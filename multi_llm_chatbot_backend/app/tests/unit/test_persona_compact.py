"""Unit tests for compact persona response shaping."""

import unittest

from app.models.persona import _ensure_compact_shape, _distinct_next_step


class TestEnsureCompactShape(unittest.TestCase):
    def test_keeps_full_thought_and_distinct_next(self):
        raw = (
            "### Thought\n"
            "Your Windows PC likely needs better backup hygiene before enabling extra MFA.\n"
            "\n"
            "### What to do\n"
            "- Turn on File History or OneDrive backup for Documents.\n"
            "- Enable MFA on email and banking accounts.\n"
            "- Update Windows and review installed apps.\n"
            "\n"
            "### Next step\n"
            "Tonight, start a full backup of Documents to an external drive.\n"
            "</END>"
        )
        out = _ensure_compact_shape(raw, "medium")
        self.assertIn("### Thought", out)
        self.assertIn("### What to do", out)
        self.assertIn("### Next step", out)
        thought = out.split("### What to do")[0]
        self.assertIn("backup hygiene", thought.lower())
        next_section = out.split("### Next step")[1].strip()
        first_bullet = "Turn on File History or OneDrive backup for Documents."
        self.assertNotEqual(next_section.lower(), first_bullet.lower())

    def test_does_not_copy_first_bullet_as_next_when_missing(self):
        raw = (
            "### Thought\n"
            "Phishing risk is elevated after the click.\n"
            "\n"
            "### What to do\n"
            "- Change the password on the affected account.\n"
            "- Revoke active sessions.\n"
            "- Scan the device for malware.\n"
        )
        out = _ensure_compact_shape(raw, "medium")
        next_section = out.split("### Next step")[1].strip().lower()
        self.assertNotEqual(next_section, "change the password on the affected account.")
        self.assertTrue(next_section.startswith("begin with") or "start now" in next_section)

    def test_moves_action_bullets_out_of_thought(self):
        raw = (
            "### Thought\n"
            "Account recovery should be prioritized.\n"
            "- Reset email password immediately.\n"
            "- Enable MFA afterward.\n"
            "\n"
            "### What to do\n"
            "- Review mailbox forwarding rules.\n"
            "\n"
            "### Next step\n"
            "Reset the email password from a known-clean device.\n"
        )
        out = _ensure_compact_shape(raw, "medium")
        what = out.split("### What to do")[1].split("### Next step")[0]
        self.assertIn("Reset email password", what)
        thought = out.split("### What to do")[0]
        self.assertNotIn("- Reset email password", thought)

    def test_distinct_helper_rejects_duplicates(self):
        bullets = ["Enable MFA on email", "Update passwords", "Back up files"]
        result = _distinct_next_step("Enable MFA on email", bullets, "fallback", 40)
        self.assertNotEqual(result.lower(), "enable mfa on email")


if __name__ == "__main__":
    unittest.main()
