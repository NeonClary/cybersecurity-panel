"""Unit tests for model health classification helpers."""

import unittest

from app.core.model_status import (
    classify_probe_exception,
    classify_probe_text,
    truncate_error,
)


class TestClassifyProbeText(unittest.TestCase):
    def test_online_ok_word(self):
        status, err = classify_probe_text("OK")
        self.assertEqual(status, "online")
        self.assertIsNone(err)

    def test_online_with_whitespace_and_punctuation(self):
        status, err = classify_probe_text("  ok.\n")
        self.assertEqual(status, "online")
        self.assertIsNone(err)

    def test_unavailable_none(self):
        status, err = classify_probe_text(None)
        self.assertEqual(status, "unavailable")
        self.assertIsNone(err)

    def test_unavailable_empty(self):
        status, err = classify_probe_text("   ")
        self.assertEqual(status, "unavailable")
        self.assertIsNone(err)

    def test_error_soft_fail_message(self):
        status, err = classify_probe_text(
            "I'm unable to connect to the AI service. Please ensure the vLLM endpoint is available."
        )
        self.assertEqual(status, "error")
        self.assertIsNotNone(err)
        self.assertIn("unable to connect", err.lower())

    def test_error_truncated_to_200(self):
        huge = "unable to connect " + ("x" * 500)
        status, err = classify_probe_text(huge)
        self.assertEqual(status, "error")
        self.assertEqual(len(err), 200)


class TestClassifyProbeException(unittest.TestCase):
    def test_exception_is_error(self):
        status, err = classify_probe_exception(RuntimeError("HTTP 503 Service Unavailable"))
        self.assertEqual(status, "error")
        self.assertIn("503", err)

    def test_truncate_error(self):
        self.assertEqual(len(truncate_error("a" * 250)), 200)


if __name__ == "__main__":
    unittest.main()
