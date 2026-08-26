"""Goal-grounded Practical Next Steps chip and greeting generation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Union

from app.core.user_context import extract_stated_goal, has_stated_goal_or_summary

logger = logging.getLogger(__name__)

_MAX_STARTERS = 12
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_SLOT_STAGGER_SECONDS = 0.08
_SLOT_CONCURRENCY = 3
_MAX_QUESTION_WORDS = 14
_MAX_CHAT_PROMPT_WORDS = 28

DEFAULT_GREETING = "What cybersecurity problem should we work on first?"
DEFAULT_SUBHEADER = (
    "I can help with threats, controls, incidents, compliance, or your security career."
)

# Filler preambles that create a wall-of-text feel on chips.
_FILLER_OPENER_RE = re.compile(
    r"^(?:to begin(?:\s+with)?|to shape(?:\s+your\s+path)?|to start(?:\s+with)?|"
    r"to identify|to dissect|to analyze|to explore|to consider|to examine|"
    r"to discuss|let'?s|first off|as a first step|i'?d like|i would like|"
    r"so,?|now,?|here,?|for(?:\s+a)?\s+start|getting started|"
    r"to get started|to understand|in order to|when it comes to)\b[\s,:-]*",
    re.IGNORECASE,
)

# Advisor-to-user lecturing that must never be inserted into chat as the user turn.
_ADVISOR_TO_USER_RE = re.compile(
    r"(?:"
    r"\blet'?s\b|"
    r"\blet us\b|"
    r"\bhave you considered\b|"
    r"\bhave you thought\b|"
    r"\bhave you looked\b|"
    r"\byou should\b|"
    r"\byou might\b|"
    r"\byou need to\b|"
    r"\byou can start\b|"
    r"\bfor instance\b|"
    r"\bthis idea blends\b|"
    r"\bthe core concept\b|"
    r"\bto identify the\b|"
    r"\bwhich creates a unique\b"
    r")",
    re.IGNORECASE,
)

_FIRST_PERSON_RE = re.compile(r"\b(?:i|i'm|i'd|i've|i'll|my|mine)\b", re.IGNORECASE)
_SECOND_PERSON_YOUR_RE = re.compile(r"\byour\b", re.IGNORECASE)

# "For MFA,", "For backups,", "For my incident response plan,"
_TOPIC_COMMA_LEAD_RE = re.compile(
    r"^for\s+[^?]{1,48}?,\s*",
    re.IGNORECASE,
)

_PROMPT_VARIATIONS: List[str] = [
    "Start the question with How. Ask the advisor panel about the single highest-priority next step for my stated goal.",
    "Start the question with What. Ask the advisor panel about the biggest security risk I should address next.",
    "Start the question with Which. Ask the advisor panel to choose between two practical approaches for my goal.",
    "Start the question with Should. Ask the advisor panel about one concrete action I can take this week.",
    "Start the question with Where. Ask the advisor panel about a specific control, tool, or practice that fits my situation.",
    "Start the question with Can. Ask the advisor panel to explain one concept I should understand before moving forward.",
]


def _exclude_key(text: str) -> str:
    cleaned = _normalize_starter(str(text or "")).lower()
    return cleaned.rstrip(".?! ").strip()


@dataclass
class StarterSuggestion:
    lead: str
    question: str
    chat_prompt: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "lead": self.lead,
            "question": self.question,
            "chat_prompt": self.chat_prompt,
        }

    def display_text(self) -> str:
        return self.question.strip()

    def exclude_key(self) -> str:
        return _exclude_key(self.chat_prompt.strip() or self.display_text())


def _capitalize_start(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def _strip_filler_openers(text: str) -> str:
    """Remove To begin / Let's / First off style clutter only (keep goal context)."""
    cleaned = " ".join((text or "").strip().strip("\"'").split())
    prev = None
    while cleaned and cleaned != prev:
        prev = cleaned
        cleaned = _FILLER_OPENER_RE.sub("", cleaned).strip()
    return cleaned


def _strip_forbidden_openers(text: str) -> str:
    """Strip filler openers and 'For <topic>,' leads from chip display questions."""
    cleaned = _strip_filler_openers(text)
    prev = None
    while cleaned and cleaned != prev:
        prev = cleaned
        cleaned = _TOPIC_COMMA_LEAD_RE.sub("", cleaned).strip()
        cleaned = _FILLER_OPENER_RE.sub("", cleaned).strip()
    return _capitalize_start(cleaned)


def _normalize_starter(text: str) -> str:
    cleaned = _strip_forbidden_openers(text)
    cleaned = re.sub(r"^\d+[\.)]\s*", "", cleaned)
    return _capitalize_start(cleaned)


def _looks_like_json_payload(text: str) -> bool:
    stripped = (text or "").lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _ensure_question(text: str) -> str:
    if _looks_like_json_payload(text):
        return ""
    cleaned = _normalize_starter(text)
    if not cleaned or _looks_like_json_payload(cleaned):
        return ""
    if not cleaned.endswith("?"):
        cleaned = cleaned.rstrip(".! ") + "?"
    return cleaned


def _word_count(text: str) -> int:
    return len((text or "").split())


def _is_multi_sentence(text: str) -> bool:
    """True when the text has more than one sentence (lectures, not one ask)."""
    body = (text or "").strip()
    if body.endswith("?"):
        body = body[:-1]
    body = re.sub(r"\b(?:e\.g|i\.e|etc)\.", " ", body, flags=re.IGNORECASE)
    body = re.sub(r"\.{2,}", " ", body)
    return bool(re.search(r"[.!?]", body))


def _looks_like_advisor_to_user(text: str) -> bool:
    """True when text is an advisor lecturing/interviewing the user."""
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return False
    if _ADVISOR_TO_USER_RE.search(cleaned):
        return True
    if _is_multi_sentence(cleaned):
        return True
    if _SECOND_PERSON_YOUR_RE.search(cleaned) and not _FIRST_PERSON_RE.search(cleaned):
        return True
    return False


def _acceptable_user_chat_prompt(text: str) -> bool:
    """Accept only a single first-person question the user would send to the panel."""
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned or not cleaned.endswith("?"):
        return False
    if _looks_like_advisor_to_user(cleaned):
        return False
    if _word_count(cleaned) > _MAX_CHAT_PROMPT_WORDS * 2:
        return False
    return True


def _ensure_chat_question(text: str) -> str:
    if _looks_like_json_payload(text):
        return ""
    cleaned = _strip_filler_openers(text)
    if not cleaned or _looks_like_json_payload(cleaned):
        return ""
    if not cleaned.endswith("?"):
        cleaned = cleaned.rstrip(".! ") + "?"
    if not _acceptable_user_chat_prompt(cleaned):
        return ""
    return cleaned


def _synthesize_user_chat_prompt(question: str, goal: str = "") -> str:
    """Build a first-person user question to the advisor panel from chip + goal."""
    question = _ensure_question(question)
    if not question:
        return ""
    if goal:
        snippet = goal.strip().rstrip(".")
        if len(snippet) > 60:
            snippet = snippet[:57].rstrip() + "..."
        lowered_q = question[0].lower() + question[1:]
        lowered_g = snippet[0].lower() + snippet[1:]
        synthesized = f"Given my goal to {lowered_g}, {lowered_q}"
        if _looks_like_advisor_to_user(synthesized) and _looks_like_advisor_to_user(question):
            return f"Given my goal to {lowered_g}, what should I ask the advisor panel first?"
        return synthesized
    if _looks_like_advisor_to_user(question):
        return ""
    return question


def _build_chat_prompt(question: str, goal: str = "", provided: str = "") -> str:
    question = _ensure_question(question)
    if not question:
        return ""
    provided_chat = _ensure_chat_question(provided) if provided else ""
    if provided_chat:
        return provided_chat
    return _synthesize_user_chat_prompt(question, goal)


def _normalize_suggestion_obj(raw: Any, goal: str = "") -> Optional[StarterSuggestion]:
    if isinstance(raw, str):
        stripped = raw.strip()
        if _looks_like_json_payload(stripped):
            partial_q = _partial_question_from_stream(stripped)
            if not partial_q:
                return None
            stripped = partial_q
        question = _ensure_question(stripped)
        if not question:
            return None
        chat = _build_chat_prompt(question, goal)
        return StarterSuggestion(lead="", question=question, chat_prompt=chat)

    if not isinstance(raw, dict):
        return None

    question = _ensure_question(str(raw.get("question") or raw.get("text") or ""))
    if not question:
        return None
    chat = _build_chat_prompt(
        question,
        goal,
        provided=str(raw.get("chat_prompt") or ""),
    )
    return StarterSuggestion(lead="", question=question, chat_prompt=chat)


def _parse_suggestions(raw: str, goal: str = "") -> List[StarterSuggestion]:
    cleaned = (raw or "").strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned).strip()
    match = _JSON_OBJECT_RE.search(cleaned)
    if match:
        cleaned = match.group(0)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        array_match = _JSON_ARRAY_RE.search(cleaned)
        if not array_match:
            return []
        try:
            parsed = json.loads(array_match.group(0))
        except json.JSONDecodeError:
            return []

    items: Any
    if isinstance(parsed, dict):
        items = parsed.get("suggestions") or parsed.get("items") or [parsed]
    elif isinstance(parsed, list):
        items = parsed
    else:
        return []

    if not isinstance(items, list):
        items = [items]

    out: List[StarterSuggestion] = []
    for item in items:
        suggestion = _normalize_suggestion_obj(item, goal)
        if suggestion:
            out.append(suggestion)
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


def _variation_prompt(variation_index: int) -> str:
    return _PROMPT_VARIATIONS[variation_index % len(_PROMPT_VARIATIONS)]


def _voice_rules_block() -> str:
    return (
        "You write questions the USER will send to a panel of expert "
        "cybersecurity advisors. You are not the advisor.\n"
        "Both question and chat_prompt MUST be in the user's first-person voice "
        "(I/my), addressed to the expert panel.\n"
        "Do not analyze, lecture, interview, or ask the user anything.\n"
        "GOOD chat_prompt: \"What is the most critical security risk if feline "
        "hackers in my sci-fi novel have cybernetic enhancements?\"\n"
        "BAD chat_prompt: \"To identify the risk in your novel, let's dissect "
        "feline hackers. Have you considered how this hybrid nature might "
        "reshape your universe?\""
    )


def _structured_rules_block() -> str:
    return (
        f"{_voice_rules_block()}\n"
        "Each suggestion is JSON with:\n"
        '- "lead": always an empty string. Do not write a lead-in sentence.\n'
        '- "question": the chip text. A concise first-person question the user '
        f"asks the advisor panel, {_MAX_QUESTION_WORDS - 6}-{_MAX_QUESTION_WORDS} words, "
        "MUST end with ?. Jump straight into the question — no preamble.\n"
        '- "chat_prompt": the message inserted into chat when the chip is clicked. '
        "Write it as the user speaking to the expert advisor panel, with brief "
        f"context from the stated goal (I/my), max {_MAX_CHAT_PROMPT_WORDS} words. "
        "Exactly one sentence ending in ?.\n"
        "The question MUST start with How, What, Which, Should, Where, or Can.\n"
        "NEVER start question or chat_prompt with: To begin, To shape, To start, "
        "To identify, To dissect, Let's, First off, I'd like, For <topic>, "
        "As a first step, or similar filler.\n"
        "Do not write topic prefixes like 'For MFA,' or 'For backups,'.\n"
        "NEVER write as the advisor talking to the user: no let's, "
        "Have you considered, you should, your novel, analysis, or follow-up "
        "questions directed at the user.\n"
        "NO rhetorical fluff. Ground every suggestion in the user's stated goal."
    )


def _one_slot_prompts(
    user_context: str,
    exclude: Sequence[str],
    *,
    variation_index: int = 0,
    category_title: str = "",
) -> tuple[str, str]:
    exclude_block = "\n".join(f"- {item}" for item in exclude if str(item).strip())
    if not exclude_block:
        exclude_block = "(none)"
    angle = _variation_prompt(variation_index)
    category_hint = ""
    if category_title and not category_title.lower().startswith("starter"):
        category_hint = (
            f"\nOptional theme hint (do not mention this title; do not use it as a prefix): "
            f"{category_title}"
        )
    system_prompt = (
        "You write one Practical Next Steps chip: a question the USER will send "
        "to a panel of expert cybersecurity advisors.\n"
        f"Angle: {angle}\n"
        f"{_structured_rules_block()}\n"
        'Respond ONLY with JSON: {"lead": "", "question": "...", "chat_prompt": "..."}'
    )
    user_prompt = (
        "Write a question I would type to the expert advisor panel about my "
        "stated goal. First person (I/my). Do not write analysis or questions "
        "directed at me.\n\n"
        "--- User security profile / knowledge ---\n"
        f"{(user_context or '').strip()}\n\n"
        f"{category_hint}\n"
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
    prompt_variation: Optional[int] = None,
) -> List[Dict[str, str]]:
    """Return structured starter suggestions for requested slots."""
    if llm is None or not has_stated_goal_or_summary(user_context):
        return []

    goal = extract_stated_goal(user_context or "")
    titles = [str(t).strip() for t in (category_titles or []) if str(t).strip()]
    n = len(titles) if titles else int(count or 0)
    n = max(1, min(n, _MAX_STARTERS))
    if titles:
        titles = titles[:n]
    else:
        titles = ["" for _ in range(n)]

    blocked = {
        _exclude_key(item)
        for item in (exclude or [])
        if _exclude_key(item)
    }

    # Single-slot refresh path
    if n == 1:
        variation = int(prompt_variation if prompt_variation is not None else 0)
        system_prompt, user_prompt = _one_slot_prompts(
            user_context,
            exclude or [],
            variation_index=variation,
            category_title=titles[0],
        )
        try:
            raw = await llm.generate(
                system_prompt=system_prompt,
                context=[{"role": "user", "content": user_prompt}],
                temperature=0.65,
                max_tokens=220,
                response_mime_type="application/json",
            )
            parsed = _parse_suggestions(raw, goal)
        except Exception as exc:
            logger.warning("Starter suggestion generation failed: %s", exc)
            return []
        unique: List[Dict[str, str]] = []
        for suggestion in parsed:
            key = _exclude_key(suggestion.exclude_key())
            if key in blocked:
                continue
            blocked.add(key)
            unique.append(suggestion.to_dict())
            break
        return unique

    exclude_block = "\n".join(f"- {item}" for item in (exclude or []) if str(item).strip())
    if not exclude_block:
        exclude_block = "(none)"
    angles = "\n".join(
        f"{i + 1}. {_variation_prompt(i)}" for i in range(n)
    )

    system_prompt = (
        "You write Practical Next Steps chips: questions the USER will send "
        "to a panel of expert cybersecurity advisors.\n"
        f"{_structured_rules_block()}\n"
        "Each chip must use the angle listed for its slot index.\n"
        f'Respond ONLY with valid JSON: {{"suggestions": [{n} objects]}}'
    )
    user_prompt = (
        "Write questions I would type to the expert advisor panel about my "
        "stated goal. First person (I/my). Do not write analysis or questions "
        "directed at me.\n\n"
        "--- User security profile / knowledge ---\n"
        f"{user_context.strip()}\n\n"
        "--- Slot angles (one suggestion each, same order) ---\n"
        f"{angles}\n\n"
        "--- Do not repeat any of these ---\n"
        f"{exclude_block}"
    )

    try:
        raw = await llm.generate(
            system_prompt=system_prompt,
            context=[{"role": "user", "content": user_prompt}],
            temperature=0.65,
            max_tokens=max(480, n * 140),
            response_mime_type="application/json",
        )
        suggestions = _parse_suggestions(raw, goal)
    except Exception as exc:
        logger.warning("Starter suggestion generation failed: %s", exc)
        return []

    unique: List[Dict[str, str]] = []
    seen = set(blocked)
    for suggestion in suggestions:
        key = _exclude_key(suggestion.exclude_key())
        if key in seen:
            continue
        seen.add(key)
        unique.append(suggestion.to_dict())
        if len(unique) >= n:
            break
    return unique


def _partial_question_from_stream(buf: str) -> str:
    match = re.search(r'"question"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', buf)
    if not match:
        return ""
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1).replace("\\\"", "\"")


async def iter_one_starter_suggestion(
    llm,
    user_context: str,
    *,
    category_title: str = "",
    exclude: Optional[Sequence[str]] = None,
    variation_index: int = 0,
) -> AsyncIterator[Union[str, StarterSuggestion]]:
    """Yield token chunks, then the parsed structured suggestion."""
    goal = extract_stated_goal(user_context or "")
    system_prompt, user_prompt = _one_slot_prompts(
        user_context,
        exclude or [],
        variation_index=variation_index,
        category_title=category_title,
    )
    stream = getattr(llm, "generate_stream", None)
    buf = ""
    if stream is None:
        text = await llm.generate(
            system_prompt=system_prompt,
            context=[{"role": "user", "content": user_prompt}],
            temperature=0.65,
            max_tokens=220,
            response_mime_type="application/json",
        )
        parsed = _parse_suggestions(text, goal)
        if parsed:
            yield parsed[0]
        return

    async for chunk in stream(
        system_prompt=system_prompt,
        context=[{"role": "user", "content": user_prompt}],
        temperature=0.65,
        max_tokens=220,
        response_mime_type="application/json",
    ):
        if not chunk:
            continue
        buf += chunk
        partial = _partial_question_from_stream(buf)
        if partial:
            yield partial
    parsed = _parse_suggestions(buf, goal)
    if parsed:
        yield parsed[0]
    elif buf.strip():
        fallback = _normalize_suggestion_obj(buf.strip(), goal)
        if fallback:
            yield fallback


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
    titles = [str(t).strip() for t in category_titles]
    if not titles:
        titles = ["Starter 1"]
    titles = titles[:_MAX_STARTERS]
    if llm is None or not has_stated_goal_or_summary(user_context):
        return

    queue: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(max(1, int(concurrency or 1)))
    lock = asyncio.Lock()
    blocked = [
        _exclude_key(item)
        for item in (exclude or [])
        if _exclude_key(item)
    ]
    finished = 0
    n = len(titles)

    async def _run_slot(slot: int, title: str) -> None:
        nonlocal finished
        if slot:
            await asyncio.sleep(stagger_seconds * min(slot, 4))
        last_partial = ""
        final: Optional[StarterSuggestion] = None
        try:
            async with sem:
                async for chunk in iter_one_starter_suggestion(
                    llm,
                    user_context,
                    category_title=title,
                    exclude=blocked,
                    variation_index=slot,
                ):
                    if isinstance(chunk, StarterSuggestion):
                        final = chunk
                    elif isinstance(chunk, str) and chunk != last_partial:
                        last_partial = chunk
                        await queue.put({"type": "delta", "slot": slot, "text": chunk})
            if final is None and last_partial:
                goal = extract_stated_goal(user_context or "")
                final = _normalize_suggestion_obj(last_partial, goal)
            if final:
                blocked.append(final.exclude_key())
                await queue.put({
                    "type": "done",
                    "slot": slot,
                    "text": final.display_text(),
                    "suggestion": final.to_dict(),
                })
            else:
                await queue.put({"type": "error", "slot": slot})
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
