"""Unit tests for goal-grounded Practical Next Steps chip generation."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.core.starter_suggestions import (
    StarterSuggestion,
    _build_chat_prompt,
    _looks_like_advisor_to_user,
    _parse_suggestions,
    _strip_forbidden_openers,
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

    def test_prompt_includes_context_angles_and_exclude(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "suggestions": [
                {
                    "lead": "For my novel research,",
                    "question": "How should I research cat-hacker tradecraft?",
                    "chat_prompt": "For my novel research, how should I research cat-hacker tradecraft?",
                },
                {
                    "lead": "",
                    "question": "What is the first scene-level control I should get right?",
                    "chat_prompt": "What is the first scene-level control I should get right?",
                },
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
        self.assertIn("question", result[0])
        self.assertIn("chat_prompt", result[0])
        kwargs = llm.generate.call_args.kwargs
        self.assertIn("cats as hackers", kwargs["context"][0]["content"])
        self.assertIn("Slot angles", kwargs["context"][0]["content"])
        self.assertIn("weekly milestones", kwargs["context"][0]["content"])
        self.assertEqual(kwargs["response_mime_type"], "application/json")

    def test_single_slot_refresh_uses_variation(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "lead": "For MFA rollout,",
            "question": "What should we prioritize first?",
            "chat_prompt": "I'm rolling out MFA — what should we prioritize first?",
        }))
        result = self._run(
            generate_starter_suggestions(
                llm,
                "USER KNOWLEDGE SUMMARY: stated_goal: roll out MFA",
                count=1,
                category_titles=["Practical next steps"],
                prompt_variation=3,
            )
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["question"], "What should we prioritize first?")
        self.assertEqual(result[0]["lead"], "")
        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        user_prompt = llm.generate.call_args.kwargs["context"][0]["content"]
        self.assertIn("Practical Next Steps", system_prompt)
        self.assertIn("empty string", system_prompt.lower())
        self.assertIn("Start the question with Should", system_prompt)
        self.assertIn("expert advisor panel", system_prompt.lower())
        self.assertIn("first-person", system_prompt.lower())
        self.assertIn("have you considered", system_prompt.lower())
        self.assertIn("directed at me", user_prompt.lower())

    def test_filters_excluded_and_duplicates(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "suggestions": [
                {
                    "lead": "",
                    "question": "Help me break my custom security goal into weekly milestones?",
                    "chat_prompt": "Help me break my custom security goal into weekly milestones?",
                },
                {
                    "lead": "",
                    "question": "How do talking-cat hackers stay plausible in my novel?",
                    "chat_prompt": "How do talking-cat hackers stay plausible in my novel?",
                },
                {
                    "lead": "",
                    "question": "How do talking-cat hackers stay plausible in my novel?",
                    "chat_prompt": "How do talking-cat hackers stay plausible in my novel?",
                },
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
            [{
                "lead": "",
                "question": "How do talking-cat hackers stay plausible in my novel?",
                "chat_prompt": "How do talking-cat hackers stay plausible in my novel?",
            }],
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

    def test_strip_forbidden_openers(self):
        self.assertEqual(
            _strip_forbidden_openers("To begin, what MFA should I use?"),
            "What MFA should I use?",
        )
        self.assertEqual(
            _strip_forbidden_openers("To shape your path, how do I start?"),
            "How do I start?",
        )
        self.assertEqual(
            _strip_forbidden_openers("For MFA, what should we prioritize first?"),
            "What should we prioritize first?",
        )
        self.assertEqual(
            _strip_forbidden_openers("For backups, what should I test first?"),
            "What should I test first?",
        )

    def test_parse_structured_suggestions(self):
        raw = json.dumps({
            "suggestions": [{
                "lead": "For backups,",
                "question": "What should I test first?",
                "chat_prompt": "For my backup plan, what should I test first?",
            }],
        })
        parsed = _parse_suggestions(raw, goal="backup plan")
        self.assertEqual(len(parsed), 1)
        self.assertIsInstance(parsed[0], StarterSuggestion)
        self.assertEqual(parsed[0].lead, "")
        self.assertEqual(parsed[0].question, "What should I test first?")
        self.assertTrue(parsed[0].chat_prompt.endswith("?"))
        self.assertNotIn("For backups", parsed[0].question)

    def test_drops_lead_and_does_not_chop_question_ending(self):
        raw = json.dumps({
            "lead": "For IR,",
            "question": (
                "Which is the better first step for you: enabling MFA "
                "for your email and social media accounts or a password manager?"
            ),
            "chat_prompt": (
                "Given my goal to protect personal accounts, which should I "
                "do first: enable MFA on email and social media or set up a password manager?"
            ),
        })
        parsed = _parse_suggestions(raw, goal="incident response")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].lead, "")
        self.assertTrue(parsed[0].question.endswith("password manager?"))
        self.assertIn("social media accounts or a password manager?", parsed[0].question)

    def test_incomplete_json_does_not_become_chip_text(self):
        parsed = _parse_suggestions(
            '{"lead": "", "question": "Can you explain phishing and how it connects to MFA?", "chat_prompt": "To understand how phishing',
            goal="MFA",
        )
        self.assertEqual(len(parsed), 0)
        from app.core.starter_suggestions import _normalize_suggestion_obj
        recovered = _normalize_suggestion_obj(
            '{"lead": "", "question": "Can you explain phishing and how it connects to MFA?", "chat_prompt": "To understand how phishing',
            goal="MFA",
        )
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.question, "Can you explain phishing and how it connects to MFA?")
        self.assertFalse(recovered.question.startswith("{"))

    def test_advisor_lecture_chat_prompt_is_rewritten_as_user_question(self):
        lecture = (
            "To identify the most critical security risk in your sci-fi novel, "
            "let's dissect the core concept: feline hackers. This idea blends "
            "biological systems (cats) with cybernetic or digital elements "
            "(hacking), which creates a unique attack surface. Have you considered "
            "how this hybrid nature might reshape traditional cybersecurity "
            "strategies in your novel's universe?"
        )
        self.assertTrue(_looks_like_advisor_to_user(lecture))
        raw = json.dumps({
            "lead": "",
            "question": "What is the most critical security risk with feline hackers?",
            "chat_prompt": lecture,
        })
        parsed = _parse_suggestions(raw, goal="sci-fi novel about feline hackers")
        self.assertEqual(len(parsed), 1)
        chat = parsed[0].chat_prompt
        self.assertTrue(chat.endswith("?"))
        self.assertEqual(chat.count("?"), 1)
        self.assertFalse(_looks_like_advisor_to_user(chat))
        self.assertRegex(chat, r"(?i)\b(my|i)\b")
        self.assertNotRegex(chat, r"(?i)\blet'?s\b")
        self.assertNotRegex(chat, r"(?i)have you considered")
        self.assertNotRegex(chat, r"(?i)\byour (?:sci-fi )?novel")
        self.assertIn("feline hackers", chat.lower())
        self.assertLessEqual(len(chat.split()), 40)

    def test_good_user_voice_chat_prompt_is_kept(self):
        good = (
            "What is the most critical security risk if feline hackers in my "
            "sci-fi novel have cybernetic enhancements?"
        )
        self.assertFalse(_looks_like_advisor_to_user(good))
        raw = json.dumps({
            "lead": "",
            "question": "What is the biggest risk with feline hackers?",
            "chat_prompt": good,
        })
        parsed = _parse_suggestions(raw, goal="sci-fi novel about feline hackers")
        self.assertEqual(parsed[0].chat_prompt, good)

    def test_second_person_teaching_chat_prompt_is_rejected(self):
        teaching = (
            "What is the most critical security risk in your sci-fi novel "
            "about feline hackers?"
        )
        self.assertTrue(_looks_like_advisor_to_user(teaching))
        rewritten = _build_chat_prompt(
            "What is the most critical security risk with feline hackers?",
            goal="write a sci-fi novel about feline hackers",
            provided=teaching,
        )
        self.assertFalse(_looks_like_advisor_to_user(rewritten))
        self.assertRegex(rewritten, r"(?i)\b(my|i)\b")
        self.assertNotRegex(rewritten, r"(?i)\byour sci-fi novel")
        self.assertTrue(rewritten.endswith("?"))

    def test_batch_prompt_forbids_advisor_voice(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "suggestions": [{
                "lead": "",
                "question": "What is the biggest risk with feline hackers?",
                "chat_prompt": (
                    "What is the most critical security risk if feline hackers "
                    "in my sci-fi novel have cybernetic enhancements?"
                ),
            }],
        }))
        self._run(
            generate_starter_suggestions(
                llm,
                "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about feline hackers",
                count=2,
                category_titles=["A", "B"],
            )
        )
        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        self.assertIn("USER will send", system_prompt)
        self.assertIn("Have you considered", system_prompt)
        self.assertIn("let's", system_prompt.lower())


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
    def test_emits_stable_slot_indexes_with_structured_done(self):
        async def stream_slow(*_args, **_kwargs):
            yield '{"lead": "For backups,", "question": "First question about backups?", "chat_prompt": "For backups, what is first?"}'

        async def stream_fast(*_args, **_kwargs):
            yield '{"lead": "", "question": "Second question about MFA?", "chat_prompt": "How should I roll out MFA?"}'

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
        dones = {e["slot"]: e for e in events if e["type"] == "done"}
        self.assertEqual(set(dones), {0, 1})
        self.assertEqual(dones[0]["suggestion"]["lead"], "")
        self.assertEqual(dones[0]["text"], "First question about backups?")
        self.assertIn("question", dones[0]["suggestion"])
        self.assertEqual(dones[1]["text"], "Second question about MFA?")
