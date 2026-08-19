"""Goal-grounded Getting Started chip generation."""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Sequence

from app.core.user_context import has_stated_goal_or_summary

logger = logging.getLogger(__name__)

_MAX_STARTERS = 8
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _normalize_starter(text: str) -> str:
    cleaned = " ".join((text or "").strip().strip("\"'").split())
    return cleaned


def _parse_suggestions(raw: str) -> List[str]:
    cleaned = (raw or "").strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned).strip()
    match = _JSON_OBJECT_RE.search(cleaned)
    if match:
        cleaned = match.group(0)
    parsed = json.loads(cleaned)
    items = parsed.get("suggestions") if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        if isinstance(item, str):
            normalized = _normalize_starter(item)
            if normalized:
                out.append(normalized)
    return out


async def generate_starter_suggestions(
    llm,
    user_context: str,
    *,
    count: int = 2,
    exclude: Optional[Sequence[str]] = None,
    category_titles: Optional[Sequence[str]] = None,
) -> List[str]:
    """Return one clickable starter question per requested slot.

    Falls back to an empty list when there is no usable goal/profile, no LLM,
    or generation fails — the UI then keeps its static YAML chips.
    """
    if llm is None or not has_stated_goal_or_summary(user_context):
        return []

    titles = [str(t).strip() for t in (category_titles or []) if str(t).strip()]
    n = len(titles) if titles else int(count or 0)
    n = max(1, min(n, _MAX_STARTERS))
    if titles:
        titles = titles[:n]
    else:
        titles = [f"Starter {i + 1}" for i in range(n)]

    blocked = {
        _normalize_starter(item).lower()
        for item in (exclude or [])
        if _normalize_starter(str(item))
    }

    numbered = "\n".join(f"{i + 1}. {title}" for i, title in enumerate(titles))
    exclude_block = "\n".join(f"- {item}" for item in (exclude or []) if str(item).strip())
    if not exclude_block:
        exclude_block = "(none)"

    system_prompt = (
        "You write Getting Started chips for a cybersecurity advisor chat.\n"
        "Each chip is one first-person question the user can click and send.\n"
        "Ground every question in the user's stated goal and profile. Never "
        "invent generic enterprise/compliance topics (GDPR, HIPAA, SOC 2, org "
        "architecture) unless that is actually their goal.\n"
        "Each question is one sentence, at most 22 words, no numbering or quotes.\n"
        "Make each chip distinct and matched to its category title "
        "(directional vs practical, etc.).\n"
        f'Respond ONLY with valid JSON: {{"suggestions": [{n} strings]}}'
    )
    user_prompt = (
        "--- User security profile / knowledge ---\n"
        f"{user_context.strip()}\n\n"
        "--- Categories (one question each, same order) ---\n"
        f"{numbered}\n\n"
        "--- Do not repeat any of these ---\n"
        f"{exclude_block}"
    )

    try:
        raw = await llm.generate(
            system_prompt=system_prompt,
            context=[{"role": "user", "content": user_prompt}],
            temperature=0.6,
            max_tokens=max(256, n * 80),
            response_mime_type="application/json",
        )
        suggestions = _parse_suggestions(raw)
    except Exception as exc:
        logger.warning("Starter suggestion generation failed: %s", exc)
        return []

    unique: List[str] = []
    seen = set(blocked)
    for text in suggestions:
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
        if len(unique) >= n:
            break
    return unique
