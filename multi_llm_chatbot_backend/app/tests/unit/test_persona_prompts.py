"""Unit tests for persona prompt assembly (distinct voices, anti-echo)."""

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import yaml

from app.models.persona import (
    ANTI_ECHO_CONTRACT,
    COMPACT_MARKDOWN_V1,
    PERSONA_SLOT_HINTS,
    Persona,
    compose_response_system_prompt,
    panel_lens_reminder,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
PERSONAS_DIR = REPO_ROOT / "personas" / "cyber_advisors"
CONFIG_PATH = REPO_ROOT / "cybersecurity_config.yaml"


def _load_persona_yaml(stem: str) -> dict:
    path = PERSONAS_DIR / f"{stem}.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class TestComposeResponseSystemPrompt(unittest.TestCase):
    def test_keeps_shared_headings_and_anti_echo(self):
        prompt = compose_response_system_prompt("You are Jerry.")
        self.assertIn("### Thought", prompt)
        self.assertIn("### What to do", prompt)
        self.assertIn("### Next step", prompt)
        self.assertIn("To [verb]", prompt)
        self.assertIn(ANTI_ECHO_CONTRACT.split("\n")[0], prompt)
        self.assertIn("YOUR role only", prompt)

    def test_identity_and_slot_hint_come_after_format_contract(self):
        prompt = compose_response_system_prompt(
            "You are a threat modeler.",
            name="Threat Modeling Analyst",
            role="STRIDE, ATT&CK & Tabletop Exercises",
            persona_id="threat_modeler",
        )
        compact_at = prompt.find(COMPACT_MARKDOWN_V1[:40])
        identity_at = prompt.find("You are answering as Threat Modeling Analyst")
        slot_at = prompt.rfind("Fill slots as threat modeler")
        self.assertGreater(identity_at, compact_at)
        self.assertGreater(slot_at, compact_at)
        self.assertIn("STRIDE", prompt[slot_at:])

    def test_three_example_personas_get_distinct_slot_hints(self):
        jerry = compose_response_system_prompt(
            "base", persona_id="jerry_huaute", name="Jerry Huaute",
            role="Lead Cybersecurity Advisor",
        )
        threat = compose_response_system_prompt(
            "base", persona_id="threat_modeler", name="Threat Modeling Analyst",
            role="STRIDE",
        )
        architect = compose_response_system_prompt(
            "base", persona_id="security_architect", name="Security Architect",
            role="Zero Trust, Cloud & Identity",
        )
        self.assertIn("intake lead", jerry.lower())
        self.assertIn("stride", threat.lower())
        self.assertIn("trust boundar", architect.lower())
        jerry_slot = jerry[jerry.rfind("Fill slots as"):].lower()
        threat_slot = threat[threat.rfind("Fill slots as"):].lower()
        architect_slot = architect[architect.rfind("Fill slots as"):].lower()
        self.assertNotIn("stride", jerry_slot)
        self.assertNotIn("intake lead", threat_slot)
        self.assertNotIn("purpose/scope/basics", threat_slot)
        self.assertIn("purpose/scope/basics", architect_slot)

    def test_slot_hint_map_covers_panel_and_stays_distinct(self):
        self.assertGreaterEqual(len(PERSONA_SLOT_HINTS), 8)
        jerry = PERSONA_SLOT_HINTS["jerry_huaute"].lower()
        threat = PERSONA_SLOT_HINTS["threat_modeler"].lower()
        architect = PERSONA_SLOT_HINTS["security_architect"].lower()
        self.assertIn("clarif", jerry)
        self.assertIn("abuse", threat)
        self.assertIn("zones", architect)
        self.assertNotEqual(jerry, threat)
        self.assertNotEqual(threat, architect)

    def test_unknown_persona_id_has_no_slot_hint(self):
        prompt = compose_response_system_prompt("You are X.", persona_id="not_a_real_id")
        self.assertNotIn("Fill slots as", prompt)


class TestPanelLensReminder(unittest.TestCase):
    def test_includes_name_and_role(self):
        text = panel_lens_reminder("Jerry Huaute", "Lead Cybersecurity Advisor")
        self.assertIn("Jerry Huaute", text)
        self.assertIn("Lead Cybersecurity Advisor", text)
        self.assertIn("parallel", text.lower())

    def test_skips_non_string_name(self):
        self.assertEqual(panel_lens_reminder(MagicMock(), "STRIDE"), "")

    def test_two_personas_differ(self):
        a = panel_lens_reminder("Threat Modeling Analyst", "STRIDE")
        b = panel_lens_reminder("Security Architect", "Zero Trust, Cloud & Identity")
        self.assertNotEqual(a, b)
        self.assertIn("Threat Modeling Analyst", a)
        self.assertIn("Security Architect", b)


class TestPersonaRespondUsesComposedPrompt(unittest.TestCase):
    def test_respond_passes_anti_echo_and_slot_hint(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=(
                "### Thought\nCats would steal session tokens from unattended terminals.\n\n"
                "### What to do\n"
                "- Map the ship network as an asset list.\n"
                "- Apply STRIDE to the litter-box camera feed.\n"
                "- Draft one abuse case for physical access.\n\n"
                "### Next step\nList the three systems the cats can touch.\n"
            )
        )
        persona = Persona(
            id="threat_modeler",
            name="Threat Modeling Analyst",
            system_prompt="You are a threat modeler.",
            llm=llm,
            role="STRIDE, ATT&CK & Tabletop Exercises",
        )
        asyncio.run(persona.respond([{"role": "user", "content": "feline hackers"}]))
        passed = llm.generate.call_args.kwargs["system_prompt"]
        self.assertIn("To [verb]", passed)
        self.assertIn("Fill slots as threat modeler", passed)
        self.assertIn("Threat Modeling Analyst", passed)
        self.assertGreater(
            passed.find("Fill slots as threat modeler"),
            passed.find("### Thought"),
        )


class TestPersonaYamlDistinctness(unittest.TestCase):
    def test_persona_files_exist(self):
        self.assertTrue(PERSONAS_DIR.is_dir(), PERSONAS_DIR)
        for stem in ("jerry_huaute", "threat_modeler", "security_architect"):
            self.assertTrue((PERSONAS_DIR / f"{stem}.yaml").is_file())

    def test_jerry_is_intake_not_curriculum(self):
        prompt = _load_persona_yaml("jerry_huaute")["persona_prompt"].lower()
        self.assertIn("intake", prompt)
        self.assertIn("training-program", prompt)
        self.assertIn("lived-experience", prompt)
        self.assertIn("clarifying", prompt)

    def test_threat_modeler_is_stride_not_syllabus(self):
        prompt = _load_persona_yaml("threat_modeler")["persona_prompt"].lower()
        self.assertIn("stride", prompt)
        self.assertIn("abuse", prompt)
        self.assertIn("training syllabus", prompt)
        self.assertIn("in-world", prompt)

    def test_architect_is_trust_boundaries_not_purpose_scope(self):
        prompt = _load_persona_yaml("security_architect")["persona_prompt"].lower()
        self.assertIn("trust", prompt)
        self.assertIn("purpose/scope", prompt.replace(" / ", "/"))
        self.assertIn("in-world", prompt)
        self.assertNotIn("research vs build vs review", prompt)

    def test_shared_base_prompt_forbids_echo_openers(self):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        base = cfg["personas"]["base_prompt"]
        self.assertIn("To [verb]", base)
        self.assertIn("YOUR role only", base)
        self.assertIn("shared syllabus", base.lower())


class TestOrchestratorPanelLens(unittest.TestCase):
    def test_context_includes_distinct_panel_role(self):
        from app.core.improved_orchestrator import ImprovedChatOrchestrator
        from unittest.mock import patch

        with patch("app.core.improved_orchestrator.get_session_manager"), \
             patch("app.core.improved_orchestrator.get_context_manager"):
            orch = ImprovedChatOrchestrator(llm_client=MagicMock())
        orch.context_manager._estimate_tokens_for_messages = lambda msgs: 10
        session = MagicMock()
        session.messages = [{"role": "user", "content": "feline hackers"}]
        session.uploaded_files = []
        session.user_profile_context = ""
        session.urgency_context = ""
        session.datetime_context = ""

        threat = SimpleNamespace(
            name="Threat Modeling Analyst",
            role="STRIDE, ATT&CK & Tabletop Exercises",
            system_prompt="You are TM.",
        )
        architect = SimpleNamespace(
            name="Security Architect",
            role="Zero Trust, Cloud & Identity",
            system_prompt="You are SA.",
        )
        threat_ctx = asyncio.run(
            orch._build_enhanced_context_for_persona(session, threat, "feline hackers", "")
        )
        arch_ctx = asyncio.run(
            orch._build_enhanced_context_for_persona(session, architect, "feline hackers", "")
        )
        self.assertIn("PANEL ROLE: You are Threat Modeling Analyst", threat_ctx[0]["content"])
        self.assertIn("PANEL ROLE: You are Security Architect", arch_ctx[0]["content"])
        self.assertNotEqual(threat_ctx[0]["content"], arch_ctx[0]["content"])


if __name__ == "__main__":
    unittest.main()
