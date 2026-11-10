"""Pile persona prompts are available without the private model repo."""

import unittest
from unittest.mock import patch

from app.llm.improved_vllm_client import ImprovedVllmClient
from app.llm.neon_pile import get_pile_system_prompt, load_pile_personas
from app.llm.neon_pile_prompts import BUNDLED_PILE_PROMPTS
import app.llm.neon_pile as neon_pile


class TestBundledPilePrompt(unittest.TestCase):
    def setUp(self):
        neon_pile._PILE_CACHE.clear()

    def test_cybersecurity_expert_survives_hub_failure(self):
        with patch(
            "huggingface_hub.hf_hub_download",
            side_effect=RuntimeError("401"),
        ):
            prompt = get_pile_system_prompt(
                "BrainForge/Security",
                "CybersecurityExpert",
                revision="2026.09.30",
            )
        self.assertEqual(prompt, BUNDLED_PILE_PROMPTS["CybersecurityExpert"].strip())
        self.assertIn("cybersecurity expert", prompt.lower())
        self.assertGreater(len(prompt), 200)

    def test_vanilla_stays_empty(self):
        self.assertIsNone(
            get_pile_system_prompt("BrainForge/Security", "vanilla", revision="2026.09.30")
        )
        self.assertIsNone(get_pile_system_prompt("BrainForge/Security", None))

    def test_hub_prompt_overrides_bundle(self):
        payload = "pile:\n  persona2system:\n    CybersecurityExpert: HUB PROMPT\n"

        def _download(*_args, **_kwargs):
            path = self._tmp
            path.write_text(payload, encoding="utf-8")
            return str(path)

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            self._tmp = Path(tmp) / "config.yaml"
            with patch("huggingface_hub.hf_hub_download", side_effect=_download):
                personas = load_pile_personas("BrainForge/Security", revision="2026.09.30")
        self.assertEqual(personas["CybersecurityExpert"], "HUB PROMPT")
        self.assertIsNone(personas["vanilla"])

    @patch("app.llm.improved_vllm_client.get_context_manager")
    @patch("app.llm.improved_vllm_client.AsyncOpenAI")
    def test_advisor_request_starts_with_pile_prompt(self, _openai, _ctx):
        with patch(
            "huggingface_hub.hf_hub_download",
            side_effect=RuntimeError("401"),
        ):
            client = ImprovedVllmClient(
                api_url="https://fake.example.com/vllm0",
                api_key="test-key",
                model_name="BrainForge/Security@2026.09.30",
                neon_persona="CybersecurityExpert",
            )
            messages = client._build_messages(
                "You are Jerry Huaute.",
                [{"role": "user", "content": "What should we do first?"}],
            )
        self.assertEqual(messages[0]["role"], "system")
        self.assertTrue(messages[0]["content"].startswith("First draft your thinking"))
        self.assertEqual(messages[1]["content"], "You are Jerry Huaute.")
        self.assertEqual(messages[2]["role"], "user")
