"""Unit tests for profile / stated-goal context helpers."""

import unittest

from app.core.user_context import (
    extract_stated_goal,
    goal_aware_clarification_fallback,
    has_stated_goal_or_summary,
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
