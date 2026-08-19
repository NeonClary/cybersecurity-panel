"""Unit tests for goal-grounded Getting Started chip generation."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.core.starter_suggestions import generate_starter_suggestions


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
