"""User knowledge: fact extraction, summaries, and context selection."""

from __future__ import annotations

import asyncio
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

VALID_CATEGORIES = frozenset({"person", "organization", "environment", "needs", "preferences"})

# Neon vLLM / Ollama are treated as small-context; others get the long summary.
_DEFAULT_SMALL_CONTEXT_PROVIDERS = frozenset({"vllm", "ollama"})

# Harsh / insulting descriptors to neutralize in stored fact values.
_HARSH_TERMS = {
    "negligent": "insufficient",
    "negligence": "insufficient practices",
    "careless": "inattentive",
    "carelessly": "without adequate care",
    "incompetent": "novice",
    "incompetence": "limited proficiency",
    "stupid": "inexperienced",
    "dumb": "inexperienced",
    "lazy": "inconsistent",
    "idiot": "novice",
    "idiotic": "substandard",
    "clueless": "novice",
    "hopeless": "below basic",
    "pathetic": "substandard",
    "reckless": "high-risk",
    "recklessness": "high-risk behavior",
    "sloppy": "inconsistent",
    "useless": "ineffective",
    "moron": "novice",
    "foolish": "suboptimal",
}

EXTRACTION_SYSTEM = (
    "You extract durable facts about a cybersecurity advisory user from one message.\n"
    "Return ONLY valid JSON of the form:\n"
    '{"facts":[{"category":"person|organization|environment|needs|preferences",'
    '"key":"snake_case","value":"short string","confidence":0.0,'
    '"source":"stated|inferred","evidence":"brief quote"}]}\n'
    "Categories:\n"
    "- person: role, knowledge level, certifications, name preference, learning goals\n"
    "- organization: size, industry, IT maturity, regulations (HIPAA/SOC2/etc.)\n"
    "- environment: devices, OS (Windows/macOS/Linux), browsers, email habits, MFA status,\n"
    "  backups, home/office setup, timezone/region if offered\n"
    "- needs: immediate goals, threats/incidents, urgency\n"
    "- preferences: communication style, depth, pacing\n"
    "Rules:\n"
    "- If the user explicitly states a fact (e.g. 'I have a Windows PC'), use source='stated'.\n"
    "- If you are inferring from context, use source='inferred'.\n"
    "- Always capture OS/device/computer statements (Windows PC, MacBook, iPhone, Android, etc.).\n"
    "- Capture useful cyber context with least user effort: devices/OS, role, org size, tools,\n"
    "  threats/incidents, goals, regulations, email habits, backups, MFA.\n"
    "- Friendly personalizing detail is OK (name preference, timezone/region, learning goals).\n"
    "- Do NOT extract sensitive medical/financial minutiae, exact street addresses, SSNs, or passwords.\n"
    "- Tone: professional and non-insulting. Prefer: insufficient, non-compliant, substandard,\n"
    "  novice, below basic. NEVER use: negligent, careless, incompetent, stupid, lazy, or similar.\n"
    "If nothing useful, return {\"facts\":[]}. Do not invent unsupported facts."
)

SUMMARY_SYSTEM = (
    "You write concise user-context briefs for cybersecurity AI advisors.\n"
    "Use only the provided facts and profile. Write in third person.\n"
    "Tone: professional and respectful — describe situations and gaps, never insult character.\n"
    "Prefer language like insufficient / novice / non-compliant / below basic; "
    "never negligent / careless / incompetent / stupid / lazy.\n"
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


def sanitize_fact_language(value: str) -> str:
    """Replace harsh/insulting adjectives with professional alternatives."""
    if not value:
        return value
    out = value
    # Longer phrases first
    for harsh, soft in sorted(_HARSH_TERMS.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = re.sub(rf"\b{re.escape(harsh)}\b", soft, out, flags=re.IGNORECASE)
    return out


def _coerce_source(raw: Any, *, default: str = "inferred") -> str:
    if isinstance(raw, str) and raw.strip().lower() in ("stated", "inferred"):
        return raw.strip().lower()
    return default


_DEVICE_OS_PATTERNS: List[tuple[re.Pattern[str], str, str, str]] = [
    # pattern, category, key, value
    (re.compile(r"\bwindows\s*(?:10|11)?\s*(?:pc|computer|laptop|machine|desktop)?\b", re.I), "environment", "primary_os", "Windows PC"),
    (re.compile(r"\b(?:pc|computer|laptop|desktop)\b.*\bwindows\b|\bwindows\b.*\b(?:pc|computer|laptop|desktop)\b", re.I), "environment", "primary_os", "Windows PC"),
    (re.compile(r"\bmac(?:os|book)?\b|\bapple\s+(?:computer|laptop)\b", re.I), "environment", "primary_os", "macOS"),
    (re.compile(r"\blinux\b|\bubuntu\b|\bfedora\b", re.I), "environment", "primary_os", "Linux"),
    (re.compile(r"\biphone\b|\bios\b", re.I), "environment", "mobile_os", "iOS / iPhone"),
    (re.compile(r"\bandroid\b", re.I), "environment", "mobile_os", "Android"),
    (re.compile(r"\bchromebook\b|\bchrome\s*os\b", re.I), "environment", "primary_os", "ChromeOS"),
]


def heuristic_device_facts(message_text: str) -> List[Dict[str, Any]]:
    """Deterministic OS/device facts from clear user statements."""
    text = (message_text or "").strip()
    if not text:
        return []
    # Prefer first-person / ownership cues so we don't grab advisor mentions
    owned = bool(re.search(r"\b(i|i'?m|i'?ve|my|our|we|we'?re)\b", text, re.I))
    if not owned:
        return []
    found: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for pattern, category, key, value in _DEVICE_OS_PATTERNS:
        m = pattern.search(text)
        if not m or key in seen_keys:
            continue
        seen_keys.add(key)
        found.append({
            "category": category,
            "key": key,
            "value": value,
            "confidence": 0.95,
            "source": "stated",
            "evidence": m.group(0)[:120],
        })
    return found


async def _find_fact_by_key_source(user_id: Any, key: str, source: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    cursor = db[FACTS_COLLECTION].find({"user_id": user_id, "key": key, "source": source})
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
    key = _normalize_key(key)
    value = sanitize_fact_language(value)
    existing = await _find_fact_by_key_source(user_id, key, "inferred")
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


async def upsert_stated_fact(
    user_id: Any,
    *,
    category: FactCategory,
    key: str,
    value: str,
    evidence: Optional[str] = None,
    confidence: Optional[float] = 1.0,
) -> Dict[str, Any]:
    """Insert or update a stated fact by key; demote conflicting inferred quietly."""
    db = get_database()
    now = datetime.utcnow()
    key = _normalize_key(key)
    value = sanitize_fact_language(value)
    existing = await _find_fact_by_key_source(user_id, key, "stated")
    if existing:
        update = {
            "category": category,
            "value": value,
            "confidence": confidence if confidence is not None else 1.0,
            "evidence": evidence,
            "updated_at": now,
        }
        await db[FACTS_COLLECTION].update_one({"_id": existing["_id"]}, {"$set": update})
        existing.update(update)
        return existing
    doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "category": category,
        "key": key,
        "value": value,
        "source": "stated",
        "confidence": confidence if confidence is not None else 1.0,
        "evidence": evidence,
        "created_at": now,
        "updated_at": now,
    }
    await db[FACTS_COLLECTION].insert_one(doc)
    # Remove inferred duplicate so UI shows the stated fact cleanly
    await db[FACTS_COLLECTION].delete_many(
        {"user_id": user_id, "key": key, "source": "inferred"}
    )
    return doc


async def extract_facts_from_message(
    user_id: Any,
    message_text: str,
    llm: LLMClient,
) -> List[Dict[str, Any]]:
    """Extract facts from a user message and upsert them (stated or inferred)."""
    text = (message_text or "").strip()
    if not text:
        return []

    candidates: List[Dict[str, Any]] = []
    candidates.extend(heuristic_device_facts(text))

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
        raw = ""

    payload = _parse_json_object(raw) if raw else {}
    facts_raw = payload.get("facts") if isinstance(payload.get("facts"), list) else []
    for item in facts_raw:
        if not isinstance(item, dict):
            continue
        candidates.append(item)

    saved: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        category = _coerce_category(item.get("category"))
        key = _normalize_key(str(item.get("key") or ""))
        value = sanitize_fact_language(str(item.get("value") or "").strip())
        if not category or not key or not value:
            continue
        # Prefer first (heuristic / stated) over later duplicates
        if key in seen_keys:
            continue
        seen_keys.add(key)
        evidence = item.get("evidence")
        evidence_str = str(evidence).strip() if evidence else None
        source = _coerce_source(item.get("source"), default="inferred")
        # High-confidence explicit quotes about environment → stated
        if source == "inferred" and category == "environment" and (item.get("confidence") or 0) >= 0.85:
            source = "stated"
        if source == "stated":
            doc = await upsert_stated_fact(
                user_id,
                category=category,
                key=key,
                value=value,
                evidence=evidence_str,
                confidence=_coerce_confidence(item.get("confidence")) or 1.0,
            )
        else:
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
        short = sanitize_fact_language(str(parsed.get("short") or "").strip())
        long = sanitize_fact_language(str(parsed.get("long") or "").strip())
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


def schedule_summary_regeneration(user_id: Any) -> None:
    """Fire-and-forget dual-summary regeneration; never blocks the caller.

    Wired to the two triggers from the plan: user-session start (login /
    guest entry) and after each completed chat except the first in a
    session (see ``should_regenerate_after_chat``).
    """
    try:
        from app.core.bootstrap import chat_orchestrator

        llm = chat_orchestrator.llm_client
        if llm is None and chat_orchestrator.personas:
            llm = next(iter(chat_orchestrator.personas.values())).llm
    except Exception:
        return
    if llm is None:
        return

    async def _run() -> None:
        try:
            await regenerate_summaries(user_id, llm)
        except Exception as exc:
            LOG.warning("Background summary regeneration failed: %s", exc)

    try:
        asyncio.create_task(_run())
    except RuntimeError as exc:
        LOG.warning("Could not schedule summary regeneration: %s", exc)


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
    return await upsert_stated_fact(
        user_id,
        category=category,
        key=key,
        value=value,
        evidence=evidence,
        confidence=1.0,
    )


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
