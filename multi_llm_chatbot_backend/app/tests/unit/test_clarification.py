import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.improved_orchestrator import ImprovedChatOrchestrator


def _make_session(user_message_count=1):
    """Build a mock ConversationContext with N user messages."""
    session = MagicMock()
    session.messages = [
        {"role": "user", "content": f"message {i}"}
        for i in range(user_message_count)
    ]
    return session


def _make_mock_settings():
    """Build a mock settings object with the fields needs_clarification_improved reads."""
    settings = MagicMock()
    settings.app.title = "Test Advisory Panel"
    settings.app.subtitle = "AI-Powered Test Guidance"
    settings.orchestrator.specific_keywords = ["methodology", "theory", "research"]
    settings.orchestrator.min_words_without_keywords = 6
    settings.orchestrator.clarification_questions = ["Could you provide more details?"]
    settings.orchestrator.clarification_suggestions = ["Ask about methodology."]
    return settings


def _make_orchestrator(persona_llm=None):
    """Build an orchestrator with mocked dependencies, bypassing __init__."""
    orch = ImprovedChatOrchestrator.__new__(ImprovedChatOrchestrator)
    orch.llm_client = None
    orch.session_manager = MagicMock()
    orch.context_manager = MagicMock()

    if persona_llm is not None:
        persona = MagicMock()
        persona.name = "Dr. Test"
        persona.id = "tester"
        persona.llm = persona_llm
        orch.personas = {"tester": persona}
    else:
        orch.personas = {}

    return orch


@patch("app.core.improved_orchestrator.get_settings")
class TestNeedsClarificationImproved(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    # ------------------------------------------------------------------
    # First-message gate
    # ------------------------------------------------------------------

    def test_skips_when_session_has_multiple_user_messages(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock()
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=3)

        result = self._run(
            orch.needs_clarification_improved(session, "help")
        )

        self.assertFalse(result)
        llm.generate.assert_not_called()

    def test_proceeds_when_session_has_one_user_message(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "Clear.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        self._run(orch.needs_clarification_improved(session, "explain transformers"))

        llm.generate.assert_called_once()

    # ------------------------------------------------------------------
    # LLM happy path — clear input
    # ------------------------------------------------------------------

    def test_returns_false_when_llm_says_clear(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "The user asked about a specific topic.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "explain transformers")
        )

        self.assertFalse(result)

    # ------------------------------------------------------------------
    # LLM happy path — vague input
    # ------------------------------------------------------------------

    def test_returns_true_when_llm_says_vague(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": True,
            "reason": "Single generic word with no topic.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "help")
        )

        self.assertTrue(result)

    # ------------------------------------------------------------------
    # Strict boolean parsing
    # ------------------------------------------------------------------

    def test_rejects_string_false_and_falls_back(self, mock_settings):
        """bool("false") is True in Python; ensure string values are rejected."""
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": "false",
            "reason": "Should have been a boolean.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        orch.needs_clarification = MagicMock(return_value=False)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "something")
        )

        self.assertFalse(result)
        orch.needs_clarification.assert_called_once()

    def test_rejects_string_true_and_falls_back(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": "true",
            "reason": "Should have been a boolean.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        orch.needs_clarification = MagicMock(return_value=True)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "help")
        )

        self.assertTrue(result)
        orch.needs_clarification.assert_called_once()

    def test_rejects_missing_key_and_falls_back(self, mock_settings):
        """If the LLM omits the key entirely, fall back."""
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "reason": "Forgot the main field.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        orch.needs_clarification = MagicMock(return_value=True)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "help")
        )

        self.assertTrue(result)
        orch.needs_clarification.assert_called_once()

    # ------------------------------------------------------------------
    # Malformed JSON → fallback
    # ------------------------------------------------------------------

    def test_falls_back_on_malformed_json(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="this is not json at all")
        orch = _make_orchestrator(persona_llm=llm)
        orch.needs_clarification = MagicMock(return_value=False)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "something")
        )

        self.assertFalse(result)
        orch.needs_clarification.assert_called_once()

    # ------------------------------------------------------------------
    # LLM exception → fallback
    # ------------------------------------------------------------------

    def test_falls_back_on_llm_exception(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("connection refused"))
        orch = _make_orchestrator(persona_llm=llm)
        orch.needs_clarification = MagicMock(return_value=True)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "help")
        )

        self.assertTrue(result)
        orch.needs_clarification.assert_called_once()

    # ------------------------------------------------------------------
    # No personas registered → fallback
    # ------------------------------------------------------------------

    def test_falls_back_when_no_personas_registered(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        orch = _make_orchestrator(persona_llm=None)
        orch.needs_clarification = MagicMock(return_value=True)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(session, "help")
        )

        self.assertTrue(result)
        orch.needs_clarification.assert_called_once()

    # ------------------------------------------------------------------
    # LLM call parameters
    # ------------------------------------------------------------------

    def test_llm_called_with_json_mode_and_zero_temp(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "Clear.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        self._run(
            orch.needs_clarification_improved(session, "explain transformers")
        )

        call_kwargs = llm.generate.call_args.kwargs
        self.assertEqual(call_kwargs["temperature"], 0.0)
        self.assertEqual(call_kwargs["max_tokens"], 128)
        self.assertEqual(call_kwargs["response_mime_type"], "application/json")

    def test_system_prompt_includes_app_context(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "Clear.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        self._run(
            orch.needs_clarification_improved(session, "explain transformers")
        )

        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        self.assertIn("Test Advisory Panel", system_prompt)
        self.assertIn("AI-Powered Test Guidance", system_prompt)

    def test_system_prompt_includes_domain_keywords(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "Clear.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        self._run(
            orch.needs_clarification_improved(session, "explain transformers")
        )

        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        self.assertIn("methodology", system_prompt)
        self.assertIn("theory", system_prompt)
        self.assertIn("research", system_prompt)

    def test_system_prompt_includes_advisor_names(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "Clear.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        self._run(
            orch.needs_clarification_improved(session, "explain transformers")
        )

        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        self.assertIn("Dr. Test (tester)", system_prompt)

    def test_user_input_passed_in_user_prompt(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "Clear.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        self._run(
            orch.needs_clarification_improved(session, "explain transformers")
        )

        context = llm.generate.call_args.kwargs["context"]
        self.assertEqual(len(context), 1)
        self.assertEqual(context[0]["role"], "user")
        self.assertIn("explain transformers", context[0]["content"])

    # ------------------------------------------------------------------
    # Known goal / profile — skip clarification
    # ------------------------------------------------------------------

    def test_skips_when_user_context_has_goal_and_message_refers_to_my_goal(
        self, mock_settings
    ):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock()
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)
        user_context = (
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers"
        )

        result = self._run(
            orch.needs_clarification_improved(
                session,
                "Which advisor topics are most relevant to my goal?",
                user_context,
            )
        )

        self.assertFalse(result)
        llm.generate.assert_not_called()

    def test_skips_situation_i_described_when_goal_is_known(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock()
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(
                session,
                "What should I learn first given the situation I described?",
                "USER SECURITY PROFILE: current_goals: write a novel about cat hackers",
            )
        )

        self.assertFalse(result)
        llm.generate.assert_not_called()

    def test_still_calls_llm_for_help_even_with_goal(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "needs_clarification": False,
            "reason": "Goal is already known.",
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)
        user_context = (
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers"
        )

        self._run(orch.needs_clarification_improved(session, "help", user_context))

        llm.generate.assert_called_once()
        user_prompt = llm.generate.call_args.kwargs["context"][0]["content"]
        self.assertIn("cats as hackers", user_prompt)
        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        self.assertIn("CLEAR ENOUGH", system_prompt)

    def test_skips_llm_when_heuristic_says_input_is_specific(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock()
        orch = _make_orchestrator(persona_llm=llm)
        session = _make_session(user_message_count=1)

        result = self._run(
            orch.needs_clarification_improved(
                session, "Please explain your research methodology in detail"
            )
        )

        self.assertFalse(result)
        llm.generate.assert_not_called()


FLICKR_DNC_FOLLOWUP = (
    "Was there any US political group that was involved in the 2015/2016 incident?"
)
FLICKR_GOAL_CONTEXT = (
    "USER KNOWLEDGE SUMMARY: stated_goal: recover Flickr account photos without password"
)


def _flickr_dnc_session(include_followup=True):
    """Exact multi-turn shape: Flickr recovery, then DNC 2015–16, then follow-up."""
    session = MagicMock()
    session.messages = [
        {
            "role": "user",
            "content": "recover Flickr account without password to get pictures back",
        },
        {
            "role": "jerry_huaute",
            "content": (
                "Use Yahoo Account recovery and Flickr help to regain access. "
                "Do not try to bypass the password."
            ),
        },
        {
            "role": "user",
            "content": (
                "Was there a small group of hackers that broke into the DNC "
                "server in 2020 or 2022 or earlier?"
            ),
        },
        {
            "role": "threat_analyst",
            "content": (
                "The 2015–2016 DNC intrusion is publicly attributed to APT28 / "
                "Fancy Bear, a GRU unit, not a 2020/2022 campaign."
            ),
        },
    ]
    if include_followup:
        session.messages.append({"role": "user", "content": FLICKR_DNC_FOLLOWUP})
    session.user_profile_context = FLICKR_GOAL_CONTEXT
    return session


@patch("app.core.improved_orchestrator.get_settings")
class TestRecencyOverOriginalGoal(unittest.TestCase):
    """Follow-ups must bind 'the 2015/2016 incident' to recent DNC chat, not Flickr."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_dnc_followup_does_not_need_clarification(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock()
        orch = _make_orchestrator(persona_llm=llm)
        session = _flickr_dnc_session(include_followup=True)

        result = self._run(
            orch.needs_clarification_improved(
                session, FLICKR_DNC_FOLLOWUP, FLICKR_GOAL_CONTEXT
            )
        )

        self.assertFalse(result)
        llm.generate.assert_not_called()

    def test_dnc_followup_skips_even_if_current_message_not_yet_appended(
        self, mock_settings
    ):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock()
        orch = _make_orchestrator(persona_llm=llm)
        session = _flickr_dnc_session(include_followup=False)

        result = self._run(
            orch.needs_clarification_improved(
                session, FLICKR_DNC_FOLLOWUP, FLICKR_GOAL_CONTEXT
            )
        )

        self.assertFalse(result)
        llm.generate.assert_not_called()

    def test_clarification_generation_stays_on_dnc_not_flickr(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "question": (
                "Are you asking whether any US political group was involved in "
                "the 2015–2016 DNC intrusion attributed to APT28 / GRU?"
            ),
            "suggestions": [
                "Was CrowdStrike's APT28 / GRU attribution of the 2016 DNC hack disputed?",
                "Did any US political actors participate in the 2015/2016 DNC breach?",
                "What is publicly known versus still disputed about DNC 2016 attribution?",
                "How did US agencies describe GRU involvement in the DNC incident?",
            ],
        }))
        orch = _make_orchestrator(persona_llm=llm)
        session = _flickr_dnc_session(include_followup=True)

        result = self._run(
            orch.generate_contextual_clarification(
                FLICKR_DNC_FOLLOWUP, FLICKR_GOAL_CONTEXT, session=session
            )
        )

        blob = (result["question"] + " " + " ".join(result["suggestions"])).lower()
        self.assertTrue(any(token in blob for token in ("dnc", "gru", "2016", "apt28")))
        self.assertNotIn("flickr", blob)
        self.assertNotIn("yahoo", blob)
        self.assertNotIn("recover", blob)

        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        user_prompt = llm.generate.call_args.kwargs["context"][0]["content"]
        self.assertIn("MOST RECENT", system_prompt)
        self.assertNotIn("MUST be specific to that goal", system_prompt)
        self.assertIn("DNC", user_prompt)
        self.assertIn("GRU", user_prompt)
        combined_prompt = (system_prompt + " " + user_prompt).lower()
        self.assertNotIn("must be specific to that goal", combined_prompt)

    def test_clarification_fallback_does_not_snap_back_to_flickr(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("unavailable"))
        orch = _make_orchestrator(persona_llm=llm)
        session = _flickr_dnc_session(include_followup=True)

        result = self._run(
            orch.generate_contextual_clarification(
                FLICKR_DNC_FOLLOWUP, FLICKR_GOAL_CONTEXT, session=session
            )
        )

        blob = (result["question"] + " " + " ".join(result["suggestions"])).lower()
        self.assertTrue(any(token in blob for token in ("dnc", "gru", "2016", "apt28")))
        self.assertNotIn("flickr", blob)
        self.assertNotIn("yahoo", blob)


@patch("app.core.improved_orchestrator.get_settings")
class TestGenerateContextualClarification(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_generation_prompt_includes_user_context(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json.dumps({
            "question": "Which part of the cat-hacker novel should we harden first?",
            "suggestions": [
                "Help me threat-model talking-cat hackers in the novel.",
                "What cyber concepts fit a heist told through cats?",
                "How do I keep the hacker-cats technically plausible?",
                "Which advisor should review the novel's attack scenes?",
            ],
        }))
        orch = _make_orchestrator(persona_llm=llm)
        user_context = (
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers"
        )

        result = self._run(
            orch.generate_contextual_clarification("I need a bit more direction", user_context)
        )

        self.assertIn("cat", result["question"].lower())
        user_prompt = llm.generate.call_args.kwargs["context"][0]["content"]
        self.assertIn("cats as hackers", user_prompt)
        system_prompt = llm.generate.call_args.kwargs["system_prompt"]
        self.assertIn("GDPR", system_prompt)
        self.assertIn("specific to that goal", system_prompt.lower())

    def test_fallback_stays_on_goal_when_llm_fails(self, mock_settings):
        mock_settings.return_value = _make_mock_settings()
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("unavailable"))
        orch = _make_orchestrator(persona_llm=llm)
        user_context = (
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers"
        )

        result = self._run(
            orch.generate_contextual_clarification("help", user_context)
        )

        self.assertIn("cats as hackers", result["question"].lower())
        joined = " ".join(result["suggestions"]).lower()
        self.assertNotIn("gdpr", joined)
        self.assertNotIn("hipaa", joined)
