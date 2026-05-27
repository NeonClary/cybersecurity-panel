import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_current_active_user
from app.core.database import get_database
from app.models.user import User
from app.models.user_profile import UserProfileResponse, UserProfileUpdate

LOG = logging.getLogger(__name__)

router = APIRouter()

PROFILE_FIELDS = [
    "knowledge_level",
    "timezone",
    "cyber_role",
    "organization_type",
    "primary_domains",
    "certifications",
    "tools_stack",
    "compliance_focus",
    "current_goals",
    "learning_preferences",
]

LIST_FIELDS = {"primary_domains", "certifications", "tools_stack"}

_SELECT_OPTIONS: Dict[str, List[str]] = {
    "cyber_role": [
        "Student / Learner",
        "Career changer",
        "SOC analyst",
        "Security engineer",
        "Architect / lead",
        "Manager / director",
        "Consultant",
        "Other",
    ],
    "organization_type": [
        "Startup",
        "Mid-size company",
        "Enterprise",
        "Government / public sector",
        "Education",
        "MSP / MSSP",
        "Independent / job seeker",
    ],
}


def _is_field_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return bool(value)


def enrich_profile_from_user(
    doc: Optional[Dict[str, Any]], user: User
) -> Dict[str, Any]:
    """Merge account signup fields into the profile when profile slots are empty."""
    merged = dict(doc or {})
    if user.academicStage and not _is_field_filled(merged.get("knowledge_level")):
        merged["knowledge_level"] = user.academicStage
    if user.researchArea and not _is_field_filled(merged.get("timezone")):
        merged["timezone"] = user.researchArea
    return merged


def _calc_completion(doc: Dict[str, Any]) -> int:
    filled = sum(1 for f in PROFILE_FIELDS if _is_field_filled(doc.get(f)))
    return int(filled / len(PROFILE_FIELDS) * 100)


def _profile_response(doc: Dict[str, Any], user: User) -> UserProfileResponse:
    enriched = enrich_profile_from_user(doc, user)
    fields = {k: _normalize_field(k, enriched.get(k)) for k in PROFILE_FIELDS}
    return UserProfileResponse(
        user_id=str(enriched.get("user_id", user.id)),
        **fields,
        advisor_notes=enriched.get("advisor_notes"),
        updated_at=enriched.get("updated_at"),
        completion_pct=_calc_completion(enriched),
    )


_SELECT_LOOKUP: Dict[str, Dict[str, str]] = {
    field: {opt.lower(): opt for opt in opts}
    for field, opts in _SELECT_OPTIONS.items()
}


def _normalize_select(key: str, value: str) -> str:
    lookup = _SELECT_LOOKUP.get(key)
    if not lookup or not isinstance(value, str):
        return value
    v = value.strip()
    if v.lower() in lookup:
        return lookup[v.lower()]
    for canonical_lower, canonical in lookup.items():
        if canonical_lower in v.lower():
            return canonical
    return v


def _normalize_field(key: str, value: Any) -> Any:
    if key in LIST_FIELDS:
        if isinstance(value, str):
            return [s.strip() for s in value.split(",") if s.strip()]
        if isinstance(value, list):
            return value
        return []
    if key in _SELECT_OPTIONS:
        return _normalize_select(key, value)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return value


async def _sync_profile_to_user(user: User, update_data: Dict[str, Any]) -> None:
    """Keep users.academicStage / researchArea aligned with profile edits."""
    user_updates: Dict[str, Any] = {}
    if "knowledge_level" in update_data:
        user_updates["academicStage"] = update_data["knowledge_level"] or None
    if "timezone" in update_data:
        user_updates["researchArea"] = update_data["timezone"] or None
    if user_updates:
        db = get_database()
        await db.users.update_one({"_id": user.id}, {"$set": user_updates})


@router.get("/users/me/profile", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
) -> UserProfileResponse:
    db = get_database()
    doc = await db.user_profiles.find_one({"user_id": current_user.id})
    if not doc:
        doc = {"user_id": current_user.id}
    return _profile_response(doc, current_user)


@router.put("/users/me/profile", response_model=UserProfileResponse)
async def update_my_profile(
    updates: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
) -> UserProfileResponse:
    db = get_database()
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    await db.user_profiles.update_one(
        {"user_id": current_user.id},
        {"$set": update_data, "$setOnInsert": {"user_id": current_user.id}},
        upsert=True,
    )
    await _sync_profile_to_user(current_user, update_data)
    doc = await db.user_profiles.find_one({"user_id": current_user.id}) or {
        "user_id": current_user.id
    }
    return _profile_response(doc, current_user)


class ClearDataRequest(BaseModel):
    profile: bool = False
    chats: bool = False
    canvas: bool = False


@router.post("/users/me/clear-data")
async def clear_user_data(
    req: ClearDataRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, List[str]]:
    db = get_database()
    cleared: List[str] = []

    if req.profile:
        await db.user_profiles.delete_many({"user_id": current_user.id})
        await db.onboarding_conversations.delete_many({"user_id": current_user.id})
        cleared.append("profile")

    if req.chats:
        result = await db.chat_sessions.update_many(
            {"user_id": current_user.id, "is_active": True},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )
        cleared.append(f"chats ({result.modified_count})")

    if req.canvas:
        await db.phd_canvases.delete_many({"user_id": str(current_user.id)})
        cleared.append("canvas")

    return {"cleared": cleared}
