"""Unit tests for profile / stated-goal context helpers."""

import unittest

from app.core.user_context import (
    conversation_first_clarification_fallback,
    extract_stated_goal,
    goal_aware_clarification_fallback,
    has_stated_goal_or_summary,
    history_disambiguates,
    looks_like_anaphora,
    recent_topic_competes_with_goal,
    refers_to_known_goal,
)


class TestHasStatedGoalOrSummary(unittest.TestCase):
    def test_empty(self):
        self.assertFalse(has_stated_goal_or_summary(""))
        self.assertFalse(has_stated_goal_or_summary("   "))

    def test_stated_goal_fact(self):
        self.assertTrue(
            has_stated_goal_or_summary(
                "USER KNOWLEDGE SUMMARY: stated_goal: cats as hackers"
            )
        )

    def test_current_goals_in_profile(self):
        self.assertTrue(
            has_stated_goal_or_summary(
                "USER SECURITY PROFILE: current_goals: write a sci-fi novel"
            )
        )

    def test_empty_current_goals_ignored(self):
        self.assertFalse(
            has_stated_goal_or_summary(
                "USER SECURITY PROFILE: current_goals: not specified"
            )
        )


class TestRefersToKnownGoal(unittest.TestCase):
    def test_my_goal(self):
        self.assertTrue(
            refers_to_known_goal("Which advisor topics are most relevant to my goal?")
        )

    def test_situation_described(self):
        self.assertTrue(
            refers_to_known_goal("What should I learn first given the situation I described?")
        )

    def test_what_i_shared(self):
        self.assertTrue(refers_to_known_goal("What tools best fit what I shared?"))

    def test_generic_help(self):
        self.assertFalse(refers_to_known_goal("help"))


class TestExtractAndFallback(unittest.TestCase):
    def test_extract_stated_goal(self):
        goal = extract_stated_goal(
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers"
        )
        self.assertIn("cats as hackers", goal)

    def test_fallback_mentions_goal_not_enterprise(self):
        result = goal_aware_clarification_fallback(
            "USER KNOWLEDGE SUMMARY: stated_goal: sci-fi novel about cats as hackers"
        )
        self.assertIsNotNone(result)
        self.assertIn("cats as hackers", result["question"].lower())
        joined = " ".join(result["suggestions"]).lower()
        self.assertNotIn("gdpr", joined)
        self.assertNotIn("hipaa", joined)

    def test_fallback_none_without_goal(self):
        self.assertIsNone(goal_aware_clarification_fallback(""))


class TestAnaphoraAndRecency(unittest.TestCase):
    def test_2015_2016_incident_is_anaphora(self):
        self.assertTrue(
            looks_like_anaphora(
                "Was there any US political group that was involved in the 2015/2016 incident?"
            )
        )

    def test_the_incident_is_anaphora(self):
        self.assertTrue(looks_like_anaphora("Who was behind the incident?"))

    def test_generic_help_is_not_anaphora(self):
        self.assertFalse(looks_like_anaphora("help"))

    def test_dnc_history_disambiguates_followup(self):
        messages = [
            {"role": "user", "content": "recover Flickr account without password"},
            {"role": "assistant", "content": "Use Yahoo/Flickr recovery."},
            {
                "role": "user",
                "content": "Was there a small group of hackers that broke into the DNC server?",
            },
            {
                "role": "threat_analyst",
                "content": "The 2015–2016 DNC intrusion is attributed to APT28 / GRU.",
            },
        ]
        followup = (
            "Was there any US political group that was involved in the 2015/2016 incident?"
        )
        self.assertTrue(history_disambiguates(messages, followup))
        self.assertTrue(
            recent_topic_competes_with_goal(
                messages + [{"role": "user", "content": followup}],
                followup,
                "USER KNOWLEDGE SUMMARY: stated_goal: recover Flickr account photos",
            )
        )

    def test_my_goal_does_not_compete_with_recent_topic(self):
        messages = [
            {"role": "user", "content": "recover Flickr account without password"},
            {"role": "assistant", "content": "Use Yahoo/Flickr recovery."},
            {
                "role": "user",
                "content": "Was there a small group of hackers that broke into the DNC server?",
            },
        ]
        self.assertFalse(
            recent_topic_competes_with_goal(
                messages,
                "Which advisor topics are most relevant to my goal?",
                "USER KNOWLEDGE SUMMARY: stated_goal: recover Flickr account photos",
            )
        )

    def test_conversation_fallback_stays_on_recent_topic(self):
        recent = (
            "user: Was there a small group of hackers that broke into the DNC server?\n"
            "advisor: The 2015–2016 DNC intrusion is attributed to APT28 / GRU."
        )
        result = conversation_first_clarification_fallback(
            "Was there any US political group that was involved in the 2015/2016 incident?",
            recent,
            "USER KNOWLEDGE SUMMARY: stated_goal: recover Flickr account photos",
        )
        blob = (result["question"] + " " + " ".join(result["suggestions"])).lower()
        self.assertIn("dnc", blob)
        self.assertNotIn("flickr", blob)
        self.assertNotIn("yahoo", blob)
