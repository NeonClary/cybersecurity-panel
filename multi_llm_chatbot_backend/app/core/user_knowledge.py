"""User knowledge: fact extraction, summaries, and context selection."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId

from app.config import get_settings
from app.core.database import get_database
from app.llm.llm_client import LLMClient
from app.models.user_knowledge import FactCategory

LOG = logging.getLogger(__name__)

FACTS_COLLECTION = "user_facts"
SUMMARIES_COLLECTION = "user_summaries"

VALID_CATEGORIES = frozenset({"person", "organization", "needs", "preferences"})

# Neon vLLM / Ollama are treated as small-context; others get the long summary.
_DEFAULT_SMALL_CONTEXT_PROVIDERS = frozenset({"vllm", "ollama"})

EXTRACTION_SYSTEM = (
    "You extract durable facts about a cybersecurity advisory user from one message.\n"
    "Return ONLY valid JSON of the form:\n"
    '{"facts":[{"category":"person|organization|needs|preferences",'
    '"key":"snake_case","value":"short string","confidence":0.0,'
    '"evidence":"brief quote"}]}\n'
    "Categories: person (role, knowledge, certs), organization (size, industry, IT),\n"
    "needs (immediate goal, urgency), preferences (communication, learning).\n"
    "If nothing useful, return {\"facts\":[]}. Do not invent unsupported facts."
)

SUMMARY_SYSTEM = (
    "You write concise user-context briefs for cybersecurity AI advisors.\n"
    "Use only the provided facts and profile. Write in third person.\n"
    "Return ONLY valid JSON: {\"short\":\"...\",\"long\":\"...\"}."
)


def is_small_context_provider(provider: Optional[str]) -> bool:
    """Return True when *provider* should receive the short summary."""
    if not provider:
        return True
    try:
        configured = get_settings().user_knowledge.small_context_providers
        names = {p.lower() for p in configured} if configured else set(_DEFAULT_SMALL_CONTEXT_PROVIDERS)
    except Exception:
        names = set(_DEFAULT_SMALL_CONTEXT_PROVIDERS)
    return provider.lower() in names


def should_regenerate_after_chat(session_message_count: int) -> bool:
    """Regenerate after every completed chat except the first in a session."""
    return session_message_count > 1


def _parse_json_object(raw: str) -> Dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?", "", raw or "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _normalize_key(key: str) -> str:
    key = (key or "").strip().lower()
    key = re.sub(r"[^a-z0-9_]+", "_", key)
    return key.strip("_")[:64]


def _coerce_category(raw: Any) -> Optional[FactCategory]:
    if not isinstance(raw, str):
        return None
    cat = raw.strip().lower()
    if cat in VALID_CATEGORIES:
        return cat  # type: ignore[return-value]
    return None


def _coerce_confidence(raw: Any) -> Optional[float]:
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val < 0:
        return 0.0
    if val > 1:
        return 1.0
    return val


async def _find_inferred_by_key(user_id: Any, key: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    cursor = db[FACTS_COLLECTION].find({"user_id": user_id, "key": key, "source": "inferred"})
    docs = await cursor.to_list(length=1)
    return docs[0] if docs else None


async def upsert_inferred_fact(
    user_id: Any,
    *,
    category: FactCategory,
    key: str,
    value: str,
    confidence: Optional[float] = None,
    evidence: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert or update an inferred fact with the same key for this user.

    Existing *stated* facts with the same key are left untouched; inferred
    facts are deduplicated by key only.
    """
    db = get_database()
    now = datetime.utcnow()
    existing = await _find_inferred_by_key(user_id, key)
    if existing:
        update = {
            "category": category,
            "value": value,
            "confidence": confidence,
            "evidence": evidence,
            "updated_at": now,
        }
        await db[FACTS_COLLECTION].update_one(
            {"_id": existing["_id"]},
            {"$set": update},
        )
        existing.update(update)
        return existing

    doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "category": category,
        "key": key,
        "value": value,
        "source": "inferred",
        "confidence": confidence,
        "evidence": evidence,
        "created_at": now,
        "updated_at": now,
    }
    await db[FACTS_COLLECTION].insert_one(doc)
    return doc


async def extract_facts_from_message(
    user_id: Any,
    message_text: str,
    llm: LLMClient,
) -> List[Dict[str, Any]]:
    """Extract inferred facts from a user message and upsert them."""
    text = (message_text or "").strip()
    if not text:
        return []

    try:
        raw = await llm.generate(
            system_prompt=EXTRACTION_SYSTEM,
            context=[{"role": "user", "content": text}],
            temperature=0.1,
            max_tokens=512,
            response_mime_type="application/json",
        )
    except Exception as exc:
        LOG.warning("Fact extraction LLM call failed: %s", exc)
        return []

    payload = _parse_json_object(raw)
    facts_raw = payload.get("facts")
    if not isinstance(facts_raw, list):
        return []

    saved: List[Dict[str, Any]] = []
    for item in facts_raw:
        if not isinstance(item, dict):
            continue
        category = _coerce_category(item.get("category"))
        key = _normalize_key(str(item.get("key") or ""))
        value = str(item.get("value") or "").strip()
        if not category or not key or not value:
            continue
        evidence = item.get("evidence")
        evidence_str = str(evidence).strip() if evidence else None
        doc = await upsert_inferred_fact(
            user_id,
            category=category,
            key=key,
            value=value,
            confidence=_coerce_confidence(item.get("confidence")),
            evidence=evidence_str,
        )
        saved.append(doc)
    return saved


async def _load_facts_and_profile(user_id: Any) -> Dict[str, Any]:
    db = get_database()
    facts = await db[FACTS_COLLECTION].find({"user_id": user_id}).to_list(length=500)
    profile = await db.user_profiles.find_one({"user_id": user_id}) or {}
    return {"facts": facts, "profile": profile}


def _format_facts_for_prompt(facts: List[Dict[str, Any]], profile: Dict[str, Any]) -> str:
    lines: List[str] = []
    profile_bits = []
    for key in (
        "knowledge_level",
        "cyber_role",
        "organization_type",
        "primary_domains",
        "certifications",
        "tools_stack",
        "compliance_focus",
        "current_goals",
        "learning_preferences",
        "timezone",
    ):
        val = profile.get(key)
        if val:
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            profile_bits.append(f"{key}={val}")
    if profile_bits:
        lines.append("Stated profile: " + "; ".join(profile_bits))

    for doc in facts:
        src = doc.get("source", "?")
        cat = doc.get("category", "?")
        key = doc.get("key", "?")
        value = doc.get("value", "")
        conf = doc.get("confidence")
        conf_s = f" conf={conf}" if conf is not None else ""
        lines.append(f"[{src}/{cat}] {key}={value}{conf_s}")

    return "\n".join(lines) if lines else "(no facts yet)"


async def regenerate_summaries(user_id: Any, llm: LLMClient) -> Dict[str, Any]:
    """Build short and long summaries from facts + profile; store in user_summaries."""
    settings = get_settings().user_knowledge
    bundle = await _load_facts_and_profile(user_id)
    material = _format_facts_for_prompt(bundle["facts"], bundle["profile"])

    user_prompt = (
        f"Write two summaries of this cybersecurity advisory user.\n"
        f"- short: essentials only (~{settings.short_summary_max_tokens} tokens max)\n"
        f"- long: fuller context (~{settings.long_summary_max_tokens} tokens max)\n"
        f"Include who they are, org context, maturity, current need, and prefs when known.\n\n"
        f"{material}"
    )

    short = ""
    long = ""
    try:
        raw = await llm.generate(
            system_prompt=SUMMARY_SYSTEM,
            context=[{"role": "user", "content": user_prompt}],
            temperature=0.3,
            max_tokens=settings.long_summary_max_tokens + 100,
            response_mime_type="application/json",
        )
        parsed = _parse_json_object(raw)
        short = str(parsed.get("short") or "").strip()
        long = str(parsed.get("long") or "").strip()
        if not short and not long and raw:
            # Fallback: treat entire response as long and truncate for short
            long = (raw or "").strip()
            words = long.split()
            short = " ".join(words[:80])
    except Exception as exc:
        LOG.warning("Summary regeneration LLM call failed: %s", exc)

    db = get_database()
    existing = await db[SUMMARIES_COLLECTION].find_one({"user_id": user_id})
    version = int(existing.get("version") or 0) + 1 if existing else 1
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "short": short,
        "long": long,
        "generated_at": now,
        "version": version,
    }
    await db[SUMMARIES_COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": doc, "$setOnInsert": {"user_id": user_id}},
        upsert=True,
    )
    return doc


async def get_summary_for_provider(
    user_id: Any,
    provider_or_small_context: Union[bool, str],
) -> str:
    """Return short summary when small-context, else long.

    *provider_or_small_context* may be a bool (True = small) or a provider name.
    """
    if isinstance(provider_or_small_context, bool):
        small = provider_or_small_context
    else:
        small = is_small_context_provider(str(provider_or_small_context))

    db = get_database()
    doc = await db[SUMMARIES_COLLECTION].find_one({"user_id": user_id})
    if not doc:
        return ""
    if small:
        return (doc.get("short") or doc.get("long") or "").strip()
    return (doc.get("long") or doc.get("short") or "").strip()


async def list_facts(user_id: Any, source: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_database()
    query: Dict[str, Any] = {"user_id": user_id}
    if source in ("stated", "inferred"):
        query["source"] = source
    cursor = db[FACTS_COLLECTION].find(query)
    docs = await cursor.to_list(length=500)
    docs.sort(key=lambda d: d.get("updated_at") or datetime.min, reverse=True)
    return docs


async def create_stated_fact(
    user_id: Any,
    *,
    category: FactCategory,
    key: str,
    value: str,
    evidence: Optional[str] = None,
) -> Dict[str, Any]:
    db = get_database()
    now = datetime.utcnow()
    key_n = _normalize_key(key)
    doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "category": category,
        "key": key_n,
        "value": value.strip(),
        "source": "stated",
        "confidence": 1.0,
        "evidence": evidence,
        "created_at": now,
        "updated_at": now,
    }
    await db[FACTS_COLLECTION].insert_one(doc)
    return doc


async def update_fact(
    user_id: Any,
    fact_id: Any,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    db = get_database()
    oid = fact_id if isinstance(fact_id, ObjectId) else ObjectId(str(fact_id))
    doc = await db[FACTS_COLLECTION].find_one({"_id": oid, "user_id": user_id})
    if not doc:
        return None
    clean = {k: v for k, v in updates.items() if v is not None}
    if "key" in clean:
        clean["key"] = _normalize_key(str(clean["key"]))
    if "category" in clean and clean["category"] not in VALID_CATEGORIES:
        clean.pop("category", None)
    if "source" in clean and clean["source"] not in ("stated", "inferred"):
        clean.pop("source", None)
    if not clean:
        return doc
    clean["updated_at"] = datetime.utcnow()
    await db[FACTS_COLLECTION].update_one({"_id": oid}, {"$set": clean})
    doc.update(clean)
    return doc


async def delete_fact(user_id: Any, fact_id: Any) -> bool:
    db = get_database()
    oid = fact_id if isinstance(fact_id, ObjectId) else ObjectId(str(fact_id))
    result = await db[FACTS_COLLECTION].delete_many({"_id": oid, "user_id": user_id})
    return result.deleted_count > 0


async def get_summaries_doc(user_id: Any) -> Optional[Dict[str, Any]]:
    db = get_database()
    return await db[SUMMARIES_COLLECTION].find_one({"user_id": user_id})
