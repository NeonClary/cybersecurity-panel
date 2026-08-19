"""Goal-grounded Getting Started chip and greeting generation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from app.core.user_context import extract_stated_goal, has_stated_goal_or_summary

logger = logging.getLogger(__name__)

_MAX_STARTERS = 12
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_SLOT_STAGGER_SECONDS = 0.08
_SLOT_CONCURRENCY = 3

DEFAULT_GREETING = "What cybersecurity problem should we work on first?"
DEFAULT_SUBHEADER = (
    "I can help with threats, controls, incidents, compliance, or your security career."
)


def _normalize_starter(text: str) -> str:
    cleaned = " ".join((text or "").strip().strip("\"'").split())
    cleaned = re.sub(r"^\d+[\.)]\s*", "", cleaned)
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


def fallback_starter_greeting(goal: str = "") -> Dict[str, str]:
    """Static greeting used when the orchestrator is slow or unavailable."""
    text = " ".join((goal or "").split()).strip().rstrip(".")
    if not text:
        return {"greeting": DEFAULT_GREETING, "subheader": DEFAULT_SUBHEADER}
    if text.lower().startswith("i "):
        greeting = f"{text} — what should we address first?"
    else:
        greeting = f"You asked me to help with {text[0].lower() + text[1:]}. What should we address first?"
    return {
        "greeting": greeting[:240],
        "subheader": (
            "I will keep this session aligned with that objective. "
            "Ask a specific question when you are ready to proceed."
        ),
    }


async def generate_starter_greeting(llm, user_context: str) -> Dict[str, str]:
    """Return greeting + 1–2 sentence subheader grounded in the user's goal."""
    goal = extract_stated_goal(user_context or "")
    fallback = fallback_starter_greeting(goal)
    if llm is None:
        return fallback

    system_prompt = (
        "You write the opening greeting for a cybersecurity advisor named "
        "AI Jerry Huaute, CISSP.\n"
        "Tone: professional, formal, direct. Not cute. Not salesy.\n"
        "greeting: one sentence inviting the user to begin, grounded in THEIR "
        "stated goal. Do not use the phrase 'You've contacted me today'.\n"
        "subheader: one or two serious sentences that set expectations for "
        "this session. No exclamation marks.\n"
        'Respond ONLY with JSON: {"greeting": "...", "subheader": "..."}'
    )
    user_prompt = (
        "--- User security profile / knowledge ---\n"
        f"{(user_context or '').strip() or '(none)'}\n\n"
        f"Stated goal snippet: {goal or '(none recorded)'}"
    )
    try:
        raw = await llm.generate(
            system_prompt=system_prompt,
            context=[{"role": "user", "content": user_prompt}],
            temperature=0.4,
            max_tokens=180,
            response_mime_type="application/json",
        )
        cleaned = re.sub(r"```(?:json)?", "", (raw or "").strip()).strip()
        match = _JSON_OBJECT_RE.search(cleaned)
        parsed = json.loads(match.group(0) if match else cleaned)
        greeting = _normalize_starter(str(parsed.get("greeting") or ""))
        subheader = " ".join(str(parsed.get("subheader") or "").split()).strip()
        if greeting:
            return {
                "greeting": greeting[:240],
                "subheader": (subheader or fallback["subheader"])[:400],
            }
    except Exception as exc:
        logger.warning("Starter greeting generation failed: %s", exc)
    return fallback


def _one_slot_prompts(
    user_context: str,
    category_title: str,
    exclude: Sequence[str],
) -> tuple[str, str]:
    exclude_block = "\n".join(f"- {item}" for item in exclude if str(item).strip())
    if not exclude_block:
        exclude_block = "(none)"
    system_prompt = (
        "You write one Getting Started chip for a cybersecurity advisor chat.\n"
        "Output ONLY the question: first person, one sentence, at most 22 words.\n"
        "No numbering, quotes, JSON, or preamble.\n"
        "Ground it in the user's stated goal and profile. Never invent generic "
        "enterprise/compliance topics unless that is actually their goal.\n"
        f"Match this category: {category_title}"
    )
    user_prompt = (
        "--- User security profile / knowledge ---\n"
        f"{(user_context or '').strip()}\n\n"
        "--- Do not repeat ---\n"
        f"{exclude_block}"
    )
    return system_prompt, user_prompt


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


async def iter_one_starter_suggestion(
    llm,
    user_context: str,
    *,
    category_title: str,
    exclude: Optional[Sequence[str]] = None,
) -> AsyncIterator[str]:
    """Yield token chunks for a single Getting Started question."""
    system_prompt, user_prompt = _one_slot_prompts(
        user_context, category_title, exclude or [],
    )
    stream = getattr(llm, "generate_stream", None)
    if stream is None:
        text = await llm.generate(
            system_prompt=system_prompt,
            context=[{"role": "user", "content": user_prompt}],
            temperature=0.6,
            max_tokens=80,
        )
        cleaned = _normalize_starter(text)
        if cleaned:
            yield cleaned
        return
    async for chunk in stream(
        system_prompt=system_prompt,
        context=[{"role": "user", "content": user_prompt}],
        temperature=0.6,
        max_tokens=80,
    ):
        if chunk:
            yield chunk


async def iter_starter_suggestion_events(
    llm,
    user_context: str,
    *,
    category_titles: Sequence[str],
    exclude: Optional[Sequence[str]] = None,
    concurrency: int = _SLOT_CONCURRENCY,
    stagger_seconds: float = _SLOT_STAGGER_SECONDS,
) -> AsyncIterator[Dict[str, Any]]:
    """Yield NDJSON-ready events for stable slots 0..n with limited concurrency."""
    titles = [str(t).strip() or f"Starter {i + 1}" for i, t in enumerate(category_titles)]
    titles = titles[:_MAX_STARTERS]
    if not titles or llm is None or not has_stated_goal_or_summary(user_context):
        return

    queue: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(max(1, int(concurrency or 1)))
    lock = asyncio.Lock()
    blocked = [
        _normalize_starter(item)
        for item in (exclude or [])
        if _normalize_starter(str(item))
    ]
    finished = 0
    n = len(titles)

    async def _run_slot(slot: int, title: str) -> None:
        nonlocal finished
        if slot:
            await asyncio.sleep(stagger_seconds * min(slot, 4))
        buf: List[str] = []
        try:
            async with sem:
                async for chunk in iter_one_starter_suggestion(
                    llm,
                    user_context,
                    category_title=title,
                    exclude=blocked,
                ):
                    buf.append(chunk)
                    await queue.put({"type": "delta", "slot": slot, "text": chunk})
            final = _normalize_starter("".join(buf))
            await queue.put({"type": "done", "slot": slot, "text": final})
        except Exception as exc:
            logger.warning("Starter slot %s failed: %s", slot, exc)
            await queue.put({"type": "error", "slot": slot})
        finally:
            async with lock:
                finished += 1
                if finished >= n:
                    await queue.put(None)

    tasks = [
        asyncio.create_task(_run_slot(i, title))
        for i, title in enumerate(titles)
    ]
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
