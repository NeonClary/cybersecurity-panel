"""
OnboardingAgent — conversational profile gathering for cybersecurity advisors.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.database import get_database

LOG = logging.getLogger(__name__)

PROFILE_FIELDS: List[tuple] = [
    ("knowledge_level", "What is your cybersecurity knowledge level?",
     "Level such as newcomer, foundational, practitioner, experienced, or expert"),
    ("timezone", "What time zone are you usually in?",
     "IANA timezone or region such as America/New_York, Europe/London, UTC"),
    ("cyber_role", "What best describes your role right now?",
     "Job or learning role: student, SOC analyst, engineer, architect, manager, career changer, etc."),
    ("organization_type", "What type of organization are you in (or targeting)?",
     "Startup, enterprise, government, education, MSP, or independent/job seeker"),
    ("primary_domains", "Which security domains do you focus on most?",
     "Comma-separated areas such as network, cloud, appsec, GRC, IR, identity, OT"),
    ("certifications", "Do you hold or are you pursuing any certifications?",
     "List such as Security+, CySA+, CISSP, OSCP, CCSP, or none yet"),
    ("tools_stack", "What tools or platforms do you work with regularly?",
     "SIEM, EDR, cloud security, ticketing, SOAR, etc."),
    ("compliance_focus", "Any compliance or regulatory frameworks you care about?",
     "SOC 2, ISO 27001, NIST, HIPAA, PCI-DSS, FedRAMP, or none"),
    ("current_goals", "What are you trying to accomplish in the next few months?",
     "Incident readiness, certification, job search, architecture review, audit prep, etc."),
    ("learning_preferences", "How do you prefer to learn new security concepts?",
     "Hands-on labs, reading, videos, mentorship, certifications, capture-the-flag, etc."),
]


class OnboardingAgent:
    def __init__(self, llm: Any) -> None:
        self.llm = llm

    SKIP_SENTINEL = "__skipped__"

    @staticmethod
    def _field_has_value(val: Any) -> bool:
        if val is None:
            return False
        if isinstance(val, str):
            return bool(val.strip())
        if isinstance(val, list):
            return len(val) > 0
        return bool(val)

    async def chat(self, user_input: str, user_id: Any, existing_profile: Dict[str, Any]) -> Dict[str, Any]:
        filled = {k for k, _, _d in PROFILE_FIELDS
                  if self._field_has_value(existing_profile.get(k))}
        missing = [(k, q, desc) for k, q, desc in PROFILE_FIELDS if k not in filled]
        completion = int(len(filled) / len(PROFILE_FIELDS) * 100)
        current_field = missing[0][0] if missing else None

        extracted = await self._extract_fields(user_input, missing, current_field)

        db = get_database()
        if extracted:
            from app.api.routes.user_profile import _normalize_field
            real_values: Dict[str, Any] = {}
            skipped_keys: set = set()
            for k, v in extracted.items():
                if v == self.SKIP_SENTINEL:
                    skipped_keys.add(k)
                elif v:
                    real_values[k] = _normalize_field(k, v)

            update: Dict[str, Any] = {}
            if real_values:
                update.update(real_values)
            for sk in skipped_keys:
                update[sk] = ""

            if update:
                update["updated_at"] = datetime.utcnow()
                await db.user_profiles.update_one(
                    {"user_id": user_id},
                    {"$set": update, "$setOnInsert": {"user_id": user_id}},
                    upsert=True,
                )
                filled.update(real_values.keys())
                filled.update(skipped_keys)
                missing = [(k, q, desc) for k, q, desc in PROFILE_FIELDS if k not in filled]
                completion = int(len(filled) / len(PROFILE_FIELDS) * 100)

        if not missing:
            return {
                "reply": "Great — your security profile is complete. Your advisors will tailor depth, "
                         "examples, and next steps to your role, tools, and goals.",
                "progress": 100,
                "complete": True,
            }

        reply = await self._generate_next_question(user_input, existing_profile, filled, missing)
        return {"reply": reply, "progress": completion, "complete": False}

    async def _extract_fields(
        self, text: str, missing_fields: List[tuple], current_field: Optional[str] = None
    ) -> Dict[str, Any]:
        if not text.strip():
            return {}
        skip_instruction = ""
        if current_field:
            skip_instruction = (
                f'\nThe question just asked was about "{current_field}". '
                "If the user declines, refuses, says they don't know, says skip, "
                f'return {{"{current_field}": "__skipped__"}}.'
            )
        field_descriptions = "\n".join(f'- "{k}": {desc}' for k, _q, desc in missing_fields)
        system = (
            "Extract cybersecurity profile fields from the user's message. "
            "Return ONLY valid JSON with field names as keys. "
            "For list fields return a JSON array. "
            f"{skip_instruction}\n"
            f"Fields:\n{field_descriptions}"
        )
        try:
            raw = await self.llm.generate(
                system_prompt=system,
                context=[{"role": "user", "content": text}],
                temperature=0.1,
                max_tokens=512,
            )
            cleaned = re.sub(r"```(?:json)?", "", raw).strip()
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            LOG.warning(f"Extraction failed: {e}")
        return {}

    async def _generate_next_question(
        self, user_input: str, profile: Dict[str, Any], filled: set, missing: List[tuple]
    ) -> str:
        filled_parts: List[str] = []
        for k in filled:
            val = profile.get(k)
            if val:
                filled_parts.append(f"{k}={val}")
            else:
                filled_parts.append(f"{k}=DECLINED")
        filled_summary = ", ".join(filled_parts) or "nothing yet"
        next_field_key, next_field_q, _ = missing[0]
        system = (
            "You are a friendly cybersecurity onboarding assistant. "
            "You help users build a profile so AI security advisors can personalize answers.\n"
            "RULES:\n"
            "- Respond in exactly ONE short paragraph (2-3 sentences).\n"
            "- Briefly acknowledge what they said, then ask ONE clear question.\n"
            "- End with a question mark.\n"
            "- No headings or labels like 'Question:'.\n"
            "- If they skipped a topic, say 'No problem!' and move on.\n"
            "- Never repeat topics already gathered or declined."
        )
        user_prompt = (
            f"User just said: \"{user_input}\"\n"
            f"Already gathered: {filled_summary}\n"
            f"Next topic: {next_field_key} — {next_field_q}\n"
            "Write a warm response that acknowledges them and asks about the next topic."
        )
        try:
            reply = await self.llm.generate(
                system_prompt=system,
                context=[{"role": "user", "content": user_prompt}],
                temperature=0.7,
                max_tokens=300,
            )
            if reply and "?" not in reply:
                reply = f"{reply} {next_field_q}"
            return reply
        except Exception as e:
            LOG.error(f"Question generation failed: {e}")
            return missing[0][1] if missing else "Tell me more about your security background!"
