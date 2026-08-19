"""Helpers for treating profile / stated-goal text as conversation context."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

_GOAL_REFERENCE_RE = re.compile(
    r"\b("
    r"my goal|my custom (security )?goal|"
    r"the situation i (described|shared|mentioned)|"
    r"what i (shared|described)|"
    r"the goal i (described|shared|set|chose)"
    r")\b",
    re.IGNORECASE,
)

_EMPTY_GOAL_VALUES = frozenset({
    "", "n/a", "na", "none", "not specified", "unknown", "unspecified",
})

_STATED_GOAL_RE = re.compile(
    r"stated_goal[:\s]+(.+)",
    re.IGNORECASE,
)
_CURRENT_GOALS_RE = re.compile(
    r"current_goals:\s*([^;\n]+)",
    re.IGNORECASE,
)

# Pronouns / definite references that should bind to the latest named topic.
_ANAPHORA_RE = re.compile(
    r"("
    r"\b(?:the|this|that|those)\s+"
    r"(?:incident|breach|hack|attack|intrusion|campaign|event|situation)\b"
    r"|"
    r"\b(?:the\s+)?20\d{2}\s*/\s*20\d{2}\s+incident\b"
    r"|"
    r"\bthat one\b"
    r"|"
    r"^(?:what about|and)\s+that\??$"
    r")",
    re.IGNORECASE,
)

_GENERIC_FOLLOWUP_RE = re.compile(
    r"^(help|advice|guidance|assistance|what\??|huh\??|ok|okay|\?+|hmm)\.?$",
    re.IGNORECASE,
)

_USER_ROLES = frozenset({"user"})
_SKIP_ROLES = frozenset({"system"})

RECENCY_OVER_GOAL_RULE = (
    "Resolve pronouns and references such as \"the incident\", \"that\", "
    "\"this\", or \"the 2015/2016 incident\" against the MOST RECENT "
    "conversation turns first. The user's stated goal/profile is durable "
    "background — use it when they say \"my goal\" / \"the situation I "
    "described\", or when there is no competing recent topic. Never treat "
    "the original goal as the current question after they have shifted topics."
)


def has_stated_goal_or_summary(user_context: str) -> bool:
    """True when profile text includes a usable stated goal or knowledge summary."""
    if not isinstance(user_context, str):
        return False
    text = user_context.strip()
    if not text:
        return False
    lower = text.lower()
    if "stated_goal" in lower:
        return True
    if "user knowledge summary" in lower and len(text) > 40:
        return True
    match = _CURRENT_GOALS_RE.search(text)
    if match:
        value = match.group(1).strip().lower()
        if value not in _EMPTY_GOAL_VALUES:
            return True
    return False


def refers_to_known_goal(user_input: str) -> bool:
    """True when the message points at a previously stated goal or situation."""
    if not isinstance(user_input, str):
        return False
    return bool(_GOAL_REFERENCE_RE.search(user_input))


def looks_like_anaphora(user_input: str) -> bool:
    """True when the message likely refers to something already named in chat."""
    if not isinstance(user_input, str):
        return False
    return bool(_ANAPHORA_RE.search(user_input.strip()))


def is_truly_ambiguous_followup(user_input: str) -> bool:
    """True for empty or generic follow-ups that may still need clarification."""
    if not isinstance(user_input, str):
        return True
    text = user_input.strip()
    if not text:
        return True
    if _GENERIC_FOLLOWUP_RE.match(text):
        return True
    return len(text.split()) <= 2 and not looks_like_anaphora(text)


def extract_stated_goal(user_context: str) -> str:
    """Return a short stated-goal snippet from profile/summary text, if any."""
    if not isinstance(user_context, str):
        return ""
    text = user_context
    match = _STATED_GOAL_RE.search(text)
    if match:
        snippet = match.group(1).strip().split("\n")[0].strip(" ;.")
        if snippet.lower() not in _EMPTY_GOAL_VALUES:
            return snippet[:240]
    match = _CURRENT_GOALS_RE.search(text)
    if match:
        snippet = match.group(1).strip().strip(" ;.")
        if snippet.lower() not in _EMPTY_GOAL_VALUES:
            return snippet[:240]
    return ""


def _message_role(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    return str(message.get("role") or "").strip().lower()


def _message_content(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    return str(message.get("content") or "").strip()


def iter_conversation_messages(messages: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
    """Return non-system conversation turns in order."""
    if not messages:
        return []
    out: List[Dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = _message_role(message)
        if not role or role in _SKIP_ROLES:
            continue
        content = _message_content(message)
        if not content:
            continue
        out.append({"role": role, "content": content})
    return out


def count_user_messages(messages: Optional[Iterable[Any]]) -> int:
    return sum(1 for m in iter_conversation_messages(messages) if m["role"] in _USER_ROLES)


def count_prior_user_turns(messages: Optional[Iterable[Any]], current_input: str) -> int:
    """User turns already in the session, excluding the just-appended current one."""
    users = [m for m in iter_conversation_messages(messages) if m["role"] in _USER_ROLES]
    if not users:
        return 0
    current = (current_input or "").strip()
    if current and users[-1]["content"] == current:
        return len(users) - 1
    return len(users)


def format_recent_conversation(
    messages: Optional[Iterable[Any]],
    current_input: str = "",
    max_turns: int = 8,
    max_chars_each: int = 420,
) -> str:
    """Compact recent-turn block for classifiers, routing, and clarification."""
    turns = iter_conversation_messages(messages)
    current = (current_input or "").strip()
    if current and turns and turns[-1]["role"] in _USER_ROLES and turns[-1]["content"] == current:
        turns = turns[:-1]
    if not turns:
        return ""
    lines: List[str] = []
    for turn in turns[-max_turns:]:
        role = turn["role"]
        label = "user" if role in _USER_ROLES else "advisor"
        snippet = turn["content"].replace("\n", " ")
        if len(snippet) > max_chars_each:
            snippet = snippet[: max_chars_each - 3].rstrip() + "..."
        lines.append(f"{label}: {snippet}")
    return "\n".join(lines)


def format_latest_topic(
    messages: Optional[Iterable[Any]],
    current_input: str = "",
    max_chars_each: int = 420,
) -> str:
    """Only the most recent prior user turn and the advisor replies after it."""
    turns = iter_conversation_messages(messages)
    current = (current_input or "").strip()
    if current and turns and turns[-1]["role"] in _USER_ROLES and turns[-1]["content"] == current:
        turns = turns[:-1]
    user_indexes = [i for i, t in enumerate(turns) if t["role"] in _USER_ROLES]
    if not user_indexes:
        return ""
    latest = turns[user_indexes[-1]:]
    lines: List[str] = []
    for turn in latest:
        role = turn["role"]
        label = "user" if role in _USER_ROLES else "advisor"
        snippet = turn["content"].replace("\n", " ")
        if len(snippet) > max_chars_each:
            snippet = snippet[: max_chars_each - 3].rstrip() + "..."
        lines.append(f"{label}: {snippet}")
    return "\n".join(lines)


def history_disambiguates(
    messages: Optional[Iterable[Any]],
    current_input: str = "",
) -> bool:
    """True when recent turns already name a topic the new message can continue."""
    block = format_recent_conversation(messages, current_input=current_input)
    if not block:
        return False
    # At least one prior turn with a concrete noun phrase / named topic.
    return len(block) >= 24


def recent_topic_competes_with_goal(
    messages: Optional[Iterable[Any]],
    current_input: str,
    user_context: str = "",
) -> bool:
    """True when the latest prior topic should beat the durable stated goal."""
    if refers_to_known_goal(current_input):
        return False
    turns = iter_conversation_messages(messages)
    current = (current_input or "").strip()
    if current and turns and turns[-1]["role"] in _USER_ROLES and turns[-1]["content"] == current:
        turns = turns[:-1]
    user_indexes = [i for i, t in enumerate(turns) if t["role"] in _USER_ROLES]
    if not user_indexes:
        return False
    last_user_idx = user_indexes[-1]
    recent = " ".join(t["content"] for t in turns[last_user_idx:]).lower()
    if not recent.strip():
        return False
    goal = extract_stated_goal(user_context).lower()
    if not goal:
        return True
    goal_tokens = [t for t in re.split(r"[^a-z0-9]+", goal) if len(t) >= 4]
    if not goal_tokens:
        return True
    overlap = sum(1 for t in goal_tokens if t in recent)
    return overlap < max(1, len(goal_tokens) // 2)


def goal_aware_clarification_fallback(user_context: str) -> Optional[Dict[str, Any]]:
    """Static clarification that stays on the user's goal instead of enterprise defaults."""
    if not has_stated_goal_or_summary(user_context):
        return None
    goal = extract_stated_goal(user_context)
    short = goal if goal else "the goal you already shared"
    if len(short) > 120:
        short = short[:117].rstrip() + "..."
    question = (
        f"I already have your goal ({short}). Which part should we work on first?"
        if goal else
        "I already have the situation you described. Which part should we work on first?"
    )
    return {
        "question": question,
        "suggestions": [
            "Help me break my stated goal into the first concrete steps.",
            "Which advisor topics are most relevant to my goal?",
            "What should I learn first given the situation I described?",
            "Where am I most exposed relative to my goal, and what reduces that risk fast?",
        ],
    }


def conversation_first_clarification_fallback(
    user_input: str,
    recent_block: str,
    user_context: str = "",
) -> Optional[Dict[str, Any]]:
    """Static clarification that stays on the recent topic, not the original goal."""
    block = (recent_block or "").strip()
    if not block:
        return None
    hint = " ".join(block.split())
    if len(hint) > 180:
        hint = hint[:177].rstrip() + "..."
    return {
        "question": (
            f"Should I keep going from the recent discussion ({hint})?"
        ),
        "suggestions": [
            user_input.strip() or "Continue with the most recent topic we were discussing.",
            "Focus on attribution and who was involved in that incident.",
            "What is publicly known about that event, and what is still disputed?",
            "Go back to my original stated goal instead.",
        ],
    }
