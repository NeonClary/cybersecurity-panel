"""Seed and clear Explore-as-guest demo data for temporary guest users."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from bson import ObjectId

from app.core.database import get_database
from app.core import user_knowledge as uk
from app.models.phd_canvas import PhdCanvas

Persona = Literal["personal", "business", "other"]
SAMPLE_EVIDENCE = "guest_sample"


def resolve_persona(choice: str, free_text: Optional[str] = None) -> Persona:
    c = (choice or "").strip().lower()
    if c in ("personal", "individual", "home"):
        return "personal"
    if c in ("business", "organization", "org", "smb", "enterprise"):
        return "business"
    text = (free_text or "").lower()
    biz_keywords = (
        "business", "company", "org", "smb", "employee", "office", "audit",
        "compliance", "hipaa", "soc 2", "nist", "ciso", "it manager", "firewall",
        "vendor", "customers", "workforce",
    )
    if any(k in text for k in biz_keywords):
        return "business"
    return "other" if c in ("other", "custom", "something_else", "free") or free_text else "personal"


def _now() -> datetime:
    return datetime.utcnow()


def _msg(msg_type: str, content: str, **extra: Any) -> Dict[str, Any]:
    base = {
        "id": str(uuid4()),
        "type": msg_type,
        "content": content,
        "timestamp": _now().isoformat(),
    }
    base.update(extra)
    return base


async def seed_guest_demo(
    user_id: Any,
    persona: Persona,
    *,
    free_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Populate profile, facts, journey, chat, and canvas with rich sample data."""
    db = get_database()
    uid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    now = _now()

    if persona == "personal":
        profile = {
            "user_id": uid,
            "cyber_role": "Individual / home user",
            "knowledge_level": "Beginner",
            "organization_type": "Independent",
            "current_goals": "Harden personal accounts and backups",
            "advisor_notes": "Demo guest — Personal Digital Security sample data",
            "updated_at": now,
        }
        facts = [
            ("person", "role", "Individual securing personal devices and accounts"),
            ("person", "knowledge_level", "Beginner — comfortable with apps, newer to MFA depth"),
            ("preferences", "communication", "Plain language, step-by-step checklists"),
            ("needs", "priority", "Password manager + MFA, then reliable backups"),
            ("needs", "urgency", "Advisory — prevent problems, not mid-incident"),
            ("organization", "context", "Household / personal cloud accounts"),
        ]
        track_id = "personal_digital_security"
        checked = ["pds_pm_1", "pds_pm_2", "pds_pm_3"]
        chat_title = "Getting started with personal digital security"
        user_q = (
            "I want to stop reusing passwords and make sure I won't lose photos "
            "if my laptop dies. Where should I start?"
        )
        jerry_resp = (
            "**You've contacted me today — here's a clear starting order.**\n\n"
            "1. **Password manager** — install one you will actually use; migrate "
            "email and banking first.\n"
            "2. **MFA on email** — authenticator app beats SMS when you can.\n"
            "3. **Automated backups** — cloud or external drive for photos and tax docs, "
            "then do one restore test.\n\n"
            "I'm walking you through **Personal Digital Security** on your Journey. "
            "Ask me about MFA apps, backup tools, or phishing next."
        )
        layout = [
            {"id": "w-notes", "type": "notes", "size": "M"},
            {"id": "w-kanban", "type": "kanban", "size": "L"},
            {"id": "w-goals", "type": "goals", "size": "M"},
        ]
        states = {
            "notes": {
                "items": [
                    {
                        "id": "n1",
                        "text": "Accounts to migrate: Email, bank, Google, Apple ID, social",
                        "tag": "accounts",
                        "at": int(now.timestamp() * 1000),
                    },
                    {
                        "id": "n2",
                        "text": "Backup folders: Photos, Documents/Taxes, Desktop/Work",
                        "tag": "backups",
                        "at": int(now.timestamp() * 1000) - 60000,
                    },
                ]
            },
            "kanban": {
                "cols": [
                    {"id": "todo", "label": "To Do"},
                    {"id": "doing", "label": "Doing"},
                    {"id": "stuck", "label": "Stuck"},
                    {"id": "done", "label": "Done"},
                ],
                "cards": [
                    {"id": "c1", "title": "Install password manager", "col": "todo", "priority": "high", "meta": "this week"},
                    {"id": "c2", "title": "Enable MFA on email", "col": "todo", "priority": "high", "meta": "this week"},
                    {"id": "c3", "title": "Turn on cloud photo backup", "col": "doing", "priority": "med", "meta": "in progress"},
                ],
            },
            "goals": {
                "items": [
                    {"id": "g1", "label": "Unique passwords everywhere", "progress": 40, "due": ""},
                    {"id": "g2", "label": "Verified restore from backup", "progress": 10, "due": ""},
                ]
            },
        }
        deliverables = {
            "activeProjectId": "p-demo-personal",
            "projects": {
                "p-demo-personal": {
                    "id": "p-demo-personal",
                    "name": "Personal security checklist",
                    "templateId": "meeting-prep",
                    "sections": {
                        "agenda": "- Password manager\n- MFA on email\n- Photo backup",
                        "progress": "Installed manager; migrated 12 logins.",
                        "blockers": "Need help choosing MFA app for phone.",
                        "decisions": "Use authenticator over SMS for email.",
                        "questions": "Is a hardware key worth it for banking?",
                        "followup": "",
                    },
                    "versions": [],
                    "aiNotes": None,
                    "createdAt": int(now.timestamp() * 1000),
                }
            },
        }
        short_summary = (
            "Guest demo: beginner individual focused on passwords/MFA and backups. "
            "Prefer plain-language checklists. On Personal Digital Security track."
        )
        long_summary = short_summary + (
            " Priority accounts: email and banking. Sample Journey items for password "
            "manager and MFA already checked. Exploring the panel without a real account."
        )

    elif persona == "business":
        profile = {
            "user_id": uid,
            "cyber_role": "IT / security lead (SMB)",
            "knowledge_level": "Intermediate",
            "organization_type": "Small–mid business",
            "organization_size": "~80 employees",
            "industry": "Professional services",
            "current_goals": "IG1 hygiene and audit readiness",
            "advisor_notes": "Demo guest — CIS IG / NIST sample data",
            "updated_at": now,
        }
        facts = [
            ("person", "role", "IT manager covering security for an 80-person firm"),
            ("person", "knowledge_level", "Intermediate — knows firewalls/MFA, wants program structure"),
            ("organization", "type", "SMB professional services"),
            ("organization", "size", "~80 employees"),
            ("organization", "compliance", "Considering SOC 2 / client security questionnaires"),
            ("needs", "priority", "Essential cyber hygiene (CIS IG1) and clearer incident basics"),
            ("preferences", "communication", "Practical controls first, frameworks second"),
        ]
        track_id = "cis_ig"
        checked = ["cis_ig1_1", "cis_ig1_5", "cis_ig1_6"]
        chat_title = "SMB security baseline and IG1"
        user_q = (
            "We have about 80 people and clients are sending security questionnaires. "
            "What's the minimum stack we should finish this quarter?"
        )
        jerry_resp = (
            "**You've contacted me today — treat this as an advisory engagement.**\n\n"
            "For an ~80-person firm, finish **CIS IG1 essentials** before polish:\n"
            "- Asset inventory (devices + SaaS)\n"
            "- Unique accounts + MFA everywhere staff can\n"
            "- Least-privilege access reviews\n"
            "- Patch window + basic logging\n"
            "- Written incident contacts (who to call, in what order)\n\n"
            "Your Journey is on **CIS Controls (IG1→IG3)**. When questionnaires ask "
            "about NIST, we map IG1 practices into CSF language — don't rebuild from scratch."
        )
        layout = [
            {"id": "w-kanban", "type": "kanban", "size": "L"},
            {"id": "w-notes", "type": "notes", "size": "M"},
            {"id": "w-deadlines", "type": "deadlines", "size": "M"},
            {"id": "w-goals", "type": "goals", "size": "M"},
        ]
        states = {
            "kanban": {
                "cols": [
                    {"id": "todo", "label": "To Do"},
                    {"id": "doing", "label": "Doing"},
                    {"id": "stuck", "label": "Stuck"},
                    {"id": "done", "label": "Done"},
                ],
                "cards": [
                    {"id": "c1", "title": "Finish SaaS inventory", "col": "todo", "priority": "high", "meta": "IG1"},
                    {"id": "c2", "title": "MFA enforcement for Microsoft 365", "col": "todo", "priority": "high", "meta": "IG1"},
                    {"id": "c3", "title": "Draft IR contact tree", "col": "todo", "priority": "med", "meta": "IR"},
                    {"id": "c4", "title": "Endpoint hardening baseline", "col": "doing", "priority": "med", "meta": "in progress"},
                    {"id": "c5", "title": "Unique admin accounts", "col": "done", "priority": "low", "meta": "done"},
                ],
            },
            "notes": {
                "items": [
                    {
                        "id": "n1",
                        "text": "Questionnaire themes: MFA, backups, access reviews, vendor list, IR plan",
                        "tag": "questionnaires",
                        "at": int(now.timestamp() * 1000),
                    },
                    {
                        "id": "n2",
                        "text": "Gap vs IG1: logging retention and vulnerability scan cadence still open",
                        "tag": "gaps",
                        "at": int(now.timestamp() * 1000) - 120000,
                    },
                ]
            },
            "deadlines": [
                {
                    "id": "d1",
                    "title": "Client security questionnaire due",
                    "date": (now + timedelta(days=21)).strftime("%Y-%m-%d"),
                    "tag": "clients",
                },
                {
                    "id": "d2",
                    "title": "Quarterly access review",
                    "date": (now + timedelta(days=45)).strftime("%Y-%m-%d"),
                    "tag": "access",
                },
            ],
            "goals": {
                "items": [
                    {"id": "g1", "label": "Complete CIS IG1 checklist", "progress": 35, "due": ""},
                    {"id": "g2", "label": "Reusable questionnaire packet", "progress": 15, "due": ""},
                ]
            },
        }
        deliverables = {
            "activeProjectId": "p-demo-biz",
            "projects": {
                "p-demo-biz": {
                    "id": "p-demo-biz",
                    "name": "Incident response one-pager",
                    "templateId": "thesis-chapter",
                    "sections": {
                        "overview": "Sample IR one-pager for demo org (80-person SMB). Written after a phishing near-miss.",
                        "background": "Day 0 09:14 phishing email reported; 09:40 credentials reset; 10:05 mailbox rules checked; 11:00 all-clear.",
                        "methods": "One user account briefly at risk. No data accessed; 45 minutes of IT time.",
                        "results": "No MFA on legacy webmail path — the gap that made the phish viable.",
                        "discussion": "MFA enforced on all mail access (owner: IT, done). Tabletop exercise with leadership in Q2.",
                    },
                    "versions": [],
                    "aiNotes": None,
                    "createdAt": int(now.timestamp() * 1000),
                },
                "p-demo-policy": {
                    "id": "p-demo-policy",
                    "name": "Acceptable use policy",
                    "templateId": "nsf-grfp",
                    "sections": {
                        "personal": "Purpose: protect company and client data. Applies to all staff, contractors, devices, and SaaS in use at the firm.",
                        "research": "1. MFA is required for email and all admin access.\n2. Company data stays in approved SaaS only.\n3. Suspected incidents are reported to IT within 1 hour.\nExceptions: written IT approval, expires in 90 days. Owner: IT; reviewed annually.",
                    },
                    "versions": [],
                    "aiNotes": None,
                    "createdAt": int(now.timestamp() * 1000),
                },
            },
        }
        short_summary = (
            "Guest demo: SMB IT lead (~80 people) aiming for CIS IG1 and questionnaire readiness. "
            "Practical controls preferred."
        )
        long_summary = short_summary + (
            " Industry professional services; MFA and access hygiene underway. Sample Journey "
            "checks inventory-related IG1 items. Exploring without a production account."
        )

    else:  # other / free-text
        goal = (free_text or "Explore cybersecurity advisory with a custom goal").strip()
        profile = {
            "user_id": uid,
            "cyber_role": "Explorer",
            "knowledge_level": "Intermediate",
            "organization_type": "Not specified",
            "current_goals": goal[:400],
            "advisor_notes": f"Demo guest free-text intake: {goal[:200]}",
            "updated_at": now,
        }
        facts = [
            ("needs", "stated_goal", goal[:500]),
            ("person", "role", "Guest explorer (custom goal)"),
            ("preferences", "communication", "Adapt depth to the goal they typed"),
            ("needs", "urgency", "Advisory / exploratory"),
        ]
        track_id = "custom_goal"
        checked: List[str] = []
        chat_title = "Your custom security goal"
        user_q = goal if len(goal) > 12 else (
            f"I'd like help with this: {goal}" if goal else
            "I'm not sure where I fit — can you help me figure out a security path?"
        )
        jerry_resp = (
            "**You've contacted me today — thank you for describing what matters.**\n\n"
            f"I heard: *{goal[:280]}*\n\n"
            "I've set your Journey to a **custom goal** track so we can break this into "
            "milestones together. Use About you to edit anything we got wrong, and ask "
            "the panel for a next concrete step — triage, tools, or a longer-term program."
        )
        layout = [
            {"id": "w-notes", "type": "notes", "size": "L"},
            {"id": "w-goals", "type": "goals", "size": "M"},
            {"id": "w-kanban", "type": "kanban", "size": "M"},
        ]
        states = {
            "notes": {
                "items": [
                    {
                        "id": "n1",
                        "text": f"Your stated goal: {goal[:800]}",
                        "tag": "goal",
                        "at": int(now.timestamp() * 1000),
                    },
                    {
                        "id": "n2",
                        "text": "Questions for the panel: What success looks like in 30 / 90 days?",
                        "tag": "framing",
                        "at": int(now.timestamp() * 1000) - 30000,
                    },
                ]
            },
            "goals": {
                "items": [
                    {"id": "g1", "label": "Clarify success criteria", "progress": 20, "due": ""},
                    {"id": "g2", "label": "First concrete control or habit", "progress": 0, "due": ""},
                ]
            },
            "kanban": {
                "cols": [
                    {"id": "todo", "label": "To Do"},
                    {"id": "doing", "label": "Doing"},
                    {"id": "stuck", "label": "Stuck"},
                    {"id": "done", "label": "Done"},
                ],
                "cards": [
                    {"id": "c1", "title": "Refine goal with Jerry", "col": "todo", "priority": "high", "meta": "today"},
                    {"id": "c2", "title": "Pick a track or keep custom", "col": "todo", "priority": "med", "meta": "this week"},
                ],
            },
        }
        deliverables = {
            "activeProjectId": "p-demo-custom",
            "projects": {
                "p-demo-custom": {
                    "id": "p-demo-custom",
                    "name": "Goal framing notes",
                    "templateId": "meeting-prep",
                    "sections": {
                        "agenda": f"- Clarify: {goal[:120]}",
                        "progress": "Just started as a guest explorer.",
                        "blockers": "Need scope (personal vs org) if still fuzzy.",
                        "decisions": "",
                        "questions": "What would make this week a win?",
                        "followup": "",
                    },
                    "versions": [],
                    "aiNotes": None,
                    "createdAt": int(now.timestamp() * 1000),
                }
            },
        }
        short_summary = f"Guest demo with custom goal: {goal[:180]}"
        long_summary = short_summary + " On custom Journey track; sample workspace seeded for exploration."

    # Profile
    await db.user_profiles.update_one(
        {"user_id": uid},
        {"$set": profile},
        upsert=True,
    )

    # Facts (mark as sample via evidence)
    for category, key, value in facts:
        await uk.create_stated_fact(
            uid,
            category=category,  # type: ignore[arg-type]
            key=key,
            value=value,
            evidence=SAMPLE_EVIDENCE,
        )

    # Summaries
    await db.user_summaries.update_one(
        {"user_id": uid},
        {
            "$set": {
                "user_id": uid,
                "short": short_summary,
                "long": long_summary,
                "generated_at": now,
                "version": 1,
                "source": SAMPLE_EVIDENCE,
            }
        },
        upsert=True,
    )

    # Journey
    await db.goal_tracks.update_one(
        {"user_id": uid},
        {
            "$set": {
                "user_id": uid,
                "active_track_id": track_id,
                "checked_item_ids": checked,
                "updated_at": now,
                "sample": True,
            }
        },
        upsert=True,
    )

    # Chat session with welcome exchange
    session = {
        "_id": ObjectId(),
        "user_id": uid,
        "title": chat_title,
        "messages": [
            _msg("user", user_q),
            _msg(
                "advisor",
                jerry_resp,
                advisorName="Jerry Huaute",
                persona_id="jerry_huaute",
                thought="Welcome the guest and give actionable next steps.",
            ),
            _msg(
                "system",
                "This is sample demo content for Explore as guest. "
                "Use Remove all sample data anytime from the user menu.",
            ),
        ],
        "created_at": now,
        "updated_at": now,
        "is_active": True,
        "sample": True,
    }
    await db.chat_sessions.insert_one(session)

    # Canvas workspace + deliverables
    canvas = PhdCanvas(user_id=uid)
    canvas.workspace = {
        "layout": layout,
        "states": states,
        "view": "workspace",
        "task_statuses": {},
    }
    canvas.deliverables = deliverables
    canvas.last_updated = now
    canvas.auto_update = False
    await db.phd_canvases.insert_one(canvas.dict(by_alias=True))

    return {
        "persona": persona,
        "track_id": track_id,
        "session_id": str(session["_id"]),
        "facts": len(facts),
    }


async def clear_guest_sample_data(user_id: Any) -> List[str]:
    """Remove seeded demo content for a user; leave the guest account intact."""
    db = get_database()
    uid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    uid_str = str(uid)
    cleared: List[str] = []

    await db.user_facts.delete_many({"user_id": uid})
    cleared.append("facts")

    await db.user_summaries.delete_many({"user_id": uid})
    cleared.append("summaries")

    await db.user_profiles.delete_many({"user_id": uid})
    await db.onboarding_conversations.delete_many({"user_id": uid})
    cleared.append("profile")

    chat_res = await db.chat_sessions.update_many(
        {"user_id": uid, "is_active": True},
        {"$set": {"is_active": False, "updated_at": _now()}},
    )
    cleared.append(f"chats ({chat_res.modified_count})")

    await db.phd_canvases.delete_many({"user_id": uid})
    await db.phd_canvases.delete_many({"user_id": uid_str})
    cleared.append("canvas")

    await db.goal_tracks.delete_many({"user_id": uid})
    await db.assessments.delete_many({"user_id": uid})
    cleared.append("journey")

    # Minimal clean guest profile so About you is not broken
    await db.user_profiles.update_one(
        {"user_id": uid},
        {
            "$set": {
                "user_id": uid,
                "advisor_notes": "Guest mode — sample data cleared",
                "updated_at": _now(),
            }
        },
        upsert=True,
    )

    return cleared
