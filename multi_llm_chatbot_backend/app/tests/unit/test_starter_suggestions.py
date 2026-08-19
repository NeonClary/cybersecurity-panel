"""Unit tests for goal-grounded Getting Started chip generation."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.core.starter_suggestions import (
    fallback_starter_greeting,
    generate_starter_greeting,
    generate_starter_suggestions,
    iter_starter_suggestion_events,
)


class TestGenerateStarterSuggestions(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_returns_empty_without_goal_or_profile(self):
        llm = MagicMock()
        llm.generate = AsyncMock()
        result = self._run(
            generate_starter_suggestions(llm, "", count=2, category_titles=["A", "B"])
        )
        self.assertEqual(result, [])
        llm.generate.assert_not_called()

    def test_returns_empty_without_llm(self):
        result = self._run(
            generate_starter_suggestions(
                None,
                "USER KNOWLEDGE SUMMARY: stated_goal: cats as hackers",
                count=2,
            )
        )
        self.assertEqual(result, [])

    def test_prompt_includes_context_categories_and_exclude(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "suggestions": [
                "How should I research cat-hacker tradecraft for my novel?",
                "What is the first scene-level control I should get right?",
            ],
        }))
        user_context = (
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers"
        )
        result = self._run(
            generate_starter_suggestions(
                llm,
                user_context,
                count=2,
                exclude=["Help me break my custom security goal into weekly milestones."],
                category_titles=["Shape your path", "Practical next steps"],
            )
        )
        self.assertEqual(len(result), 2)
        kwargs = llm.generate.call_args.kwargs
        self.assertIn("cats as hackers", kwargs["context"][0]["content"])
        self.assertIn("Shape your path", kwargs["context"][0]["content"])
        self.assertIn("Practical next steps", kwargs["context"][0]["content"])
        self.assertIn("weekly milestones", kwargs["context"][0]["content"])
        self.assertEqual(kwargs["response_mime_type"], "application/json")

    def test_filters_excluded_and_duplicates(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "suggestions": [
                "Help me break my custom security goal into weekly milestones.",
                "How do talking-cat hackers stay plausible in my novel?",
                "How do talking-cat hackers stay plausible in my novel?",
            ],
        }))
        result = self._run(
            generate_starter_suggestions(
                llm,
                "USER KNOWLEDGE SUMMARY: stated_goal: cats as hackers",
                count=2,
                exclude=["Help me break my custom security goal into weekly milestones."],
                category_titles=["Shape your path", "Practical next steps"],
            )
        )
        self.assertEqual(
            result,
            ["How do talking-cat hackers stay plausible in my novel?"],
        )

    def test_llm_failure_returns_empty(self):
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("boom"))
        result = self._run(
            generate_starter_suggestions(
                llm,
                "USER KNOWLEDGE SUMMARY: stated_goal: cats as hackers",
                count=2,
            )
        )
        self.assertEqual(result, [])


class TestStarterGreeting(unittest.TestCase):
    def test_fallback_uses_goal_without_old_contacted_copy(self):
        result = fallback_starter_greeting("Harden personal accounts and backups")
        self.assertIn("harden personal accounts", result["greeting"].lower())
        self.assertNotIn("contacted me today", result["greeting"].lower())
        self.assertTrue(result["subheader"])

    def test_fallback_without_goal(self):
        result = fallback_starter_greeting("")
        self.assertIn("cybersecurity", result["greeting"].lower())

    def test_generate_greeting_parses_json(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "greeting": "You asked me to help with the cat-hacker novel. What should we address first?",
            "subheader": "I will stay on that objective. Ask a specific research or control question.",
        }))
        result = asyncio.run(generate_starter_greeting(
            llm,
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers",
        ))
        self.assertIn("cat-hacker", result["greeting"])
        self.assertIn("objective", result["subheader"])


class TestStarterSuggestionStream(unittest.TestCase):
    def test_emits_stable_slot_indexes_even_if_second_finishes_first(self):
        async def stream_slow(*_args, **_kwargs):
            yield "First "
            yield "question about backups?"

        async def stream_fast(*_args, **_kwargs):
            yield "Second question about MFA?"

        calls = {"n": 0}

        async def generate_stream(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                async for chunk in stream_slow():
                    yield chunk
            else:
                async for chunk in stream_fast():
                    yield chunk

        llm = MagicMock()
        llm.generate_stream = generate_stream
        ctx = "USER KNOWLEDGE SUMMARY: stated_goal: harden personal accounts"

        async def collect():
            events = []
            async for event in iter_starter_suggestion_events(
                llm,
                ctx,
                category_titles=["Everyday digital safety", "Scams & phishing"],
                stagger_seconds=0,
                concurrency=2,
            ):
                events.append(event)
            return events

        events = asyncio.run(collect())
        dones = {e["slot"]: e["text"] for e in events if e["type"] == "done"}
        self.assertEqual(set(dones), {0, 1})
        self.assertIn("backups", dones[0].lower())
        self.assertIn("mfa", dones[1].lower())
        deltas = [e for e in events if e["type"] == "delta"]
        self.assertTrue(any(e["slot"] == 0 for e in deltas))
        self.assertTrue(any(e["slot"] == 1 for e in deltas))
