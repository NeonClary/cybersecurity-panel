"""Unit tests for the orchestrator routing rules (plan §5).

These cover the deterministic post-processing applied to the LLM ranking:
- the required lead advisor (Jerry) is always on the panel,
- triage mode pulls the incident expert to the front,
- invalid/duplicate IDs from the LLM are cleaned up,
- the keyword urgency fallback fires on incident language.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.core.improved_orchestrator import ImprovedChatOrchestrator


def _make_orchestrator():
    with patch("app.core.improved_orchestrator.get_session_manager"), \
         patch("app.core.improved_orchestrator.get_context_manager"):
        return ImprovedChatOrchestrator(llm_client=MagicMock())


def _pool(*ids):
    return {pid: MagicMock(id=pid) for pid in ids}


def _mock_settings(required="jerry_huaute", triage="incident_responder"):
    settings = MagicMock()
    settings.orchestrator.required_advisor = required
    settings.orchestrator.triage_advisor = triage
    settings.orchestrator.followup_count = 3
    return settings


ALL_ADVISORS = (
    "jerry_huaute", "incident_responder", "compliance_advisor",
    "security_architect", "threat_analyst", "career_mentor",
)


class TestApplyRoutingRules(unittest.TestCase):
    def setUp(self):
        self.orch = _make_orchestrator()
        self.pool = _pool(*ALL_ADVISORS)

    def _run(self, ranked, k=3, urgency="advisory", pool=None):
        with patch(
            "app.core.improved_orchestrator.get_settings",
            return_value=_mock_settings(),
        ):
            return self.orch._apply_routing_rules(
                ranked, pool or self.pool, k, urgency
            )

    def test_required_advisor_always_included(self):
        result = self._run(["threat_analyst", "security_architect", "career_mentor"])
        self.assertIn("jerry_huaute", result)
        self.assertEqual(len(result), 3)

    def test_ranking_preserved_when_required_present(self):
        ranked = ["jerry_huaute", "threat_analyst", "compliance_advisor"]
        self.assertEqual(self._run(ranked), ranked)

    def test_triage_advisor_first_on_triage(self):
        result = self._run(
            ["threat_analyst", "security_architect", "career_mentor"],
            urgency="triage",
        )
        self.assertEqual(result[0], "incident_responder")
        self.assertIn("jerry_huaute", result)

    def test_invalid_ids_filtered_and_filled(self):
        result = self._run(["not_a_persona", "threat_analyst"])
        self.assertEqual(len(result), 3)
        self.assertNotIn("not_a_persona", result)
        self.assertIn("threat_analyst", result)
        self.assertIn("jerry_huaute", result)

    def test_duplicates_removed(self):
        result = self._run(["jerry_huaute", "jerry_huaute", "threat_analyst"])
        self.assertEqual(len(result), 3)
        self.assertEqual(len(set(result)), 3)

    def test_empty_ranking_falls_back_to_pool_order(self):
        result = self._run([])
        self.assertEqual(len(result), 3)
        self.assertIn("jerry_huaute", result)

    def test_required_advisor_skipped_when_not_in_pool(self):
        pool = _pool("threat_analyst", "career_mentor")
        result = self._run(["career_mentor"], k=2, pool=pool)
        self.assertEqual(len(result), 2)
        self.assertNotIn("jerry_huaute", result)


class TestHeuristicUrgency(unittest.TestCase):
    def setUp(self):
        self.orch = _make_orchestrator()

    def test_incident_language_is_triage(self):
        for text in (
            "I think I've been hacked",
            "There is ransomware on our file server",
            "someone made an unauthorized login to my account",
            "we found a data leak",
        ):
            self.assertEqual(self.orch._heuristic_urgency(text), "triage", text)

    def test_normal_questions_are_advisory(self):
        for text in (
            "How do I prepare for a SOC 2 audit?",
            "What certification should I get first?",
            "",
        ):
            self.assertEqual(self.orch._heuristic_urgency(text), "advisory", text)


if __name__ == "__main__":
    unittest.main()
