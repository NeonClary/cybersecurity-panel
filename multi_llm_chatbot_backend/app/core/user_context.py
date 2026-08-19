"""Helpers for treating profile / stated-goal text as conversation context."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

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
