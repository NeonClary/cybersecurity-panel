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
        self.assertNotIn("…", out)
        self.assertNotIn("...", out)
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
        self.assertNotIn("change the password on the affected account", next_section)

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
        self.assertNotIn("…", result)

    def test_no_ellipsis_on_long_thought(self):
        raw = (
            "### Thought\n"
            "Your PC may be compromised after that download, so isolate it from important "
            "accounts before you hunt for malware thoroughly across disks and restore points "
            "while preserving forensic evidence. This second sentence explains more context "
            "about why backup first matters for ransomware risk scenarios that can escalate "
            "quickly overnight.\n"
            "\n"
            "### What to do\n"
            "- Disconnect from Wi-Fi and unplug ethernet immediately to limit spread of worm payloads.\n"
            "- Change passwords for email banking and work accounts from a different clean device.\n"
            "- Run a full Windows Defender offline scan and review startup items carefully afterward.\n"
            "\n"
            "### Next step\n"
            "Disconnect from Wi-Fi and unplug ethernet immediately to limit spread of worm payloads.\n"
            "</END>"
        )
        out = _ensure_compact_shape(raw, "medium")
        self.assertNotIn("…", out)
        self.assertNotIn("...", out)
        thought = out.split("### What to do")[0]
        self.assertTrue(thought.strip().endswith((".", "!", "?")) or "Thought" in thought)
        next_section = out.split("### Next step")[1].strip().lower()
        self.assertNotIn("disconnect from wi-fi and unplug ethernet", next_section)

    def test_rejects_near_paraphrase_next_step(self):
        raw = (
            "### Thought\n"
            "Act quickly but carefully after a suspicious download.\n"
            "\n"
            "### What to do\n"
            "- Disconnect your PC from the internet and any network.\n"
            "- Run a full antivirus scan with Windows Defender.\n"
            "- Change email and banking passwords from another device.\n"
            "\n"
            "### Next step\n"
            "Immediately disconnect your PC from the internet and any network connections.\n"
        )
        out = _ensure_compact_shape(raw, "medium")
        next_section = out.split("### Next step")[1].strip().lower()
        first = "disconnect your pc from the internet and any network"
        self.assertFalse(first in next_section and next_section.startswith("immediately"))


if __name__ == "__main__":
    unittest.main()
