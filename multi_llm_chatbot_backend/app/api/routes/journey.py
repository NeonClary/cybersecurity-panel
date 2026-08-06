"""Security Journey API — track definitions and per-user progress."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_active_user
from app.core.database import get_database
from app.core.tracks_loader import (
    compute_progress,
    get_track,
    list_track_summaries,
    load_tracks,
)
from app.models.journey import (
    AssessmentCreate,
    AssessmentResponse,
    Track,
    TrackSummary,
    UserTrackProgressResponse,
    UserTrackProgressUpdate,
)
from app.models.user import User

LOG = logging.getLogger(__name__)

router = APIRouter()


def _uid_str(user: User) -> str:
    return str(user.id)


def _progress_doc(user: User) -> Dict[str, Any]:
    return {
        "user_id": user.id,
        "active_track_id": None,
        "checked_item_ids": [],
        "updated_at": datetime.utcnow(),
    }


async def _get_or_create_progress(user: User) -> Dict[str, Any]:
    db = get_database()
    doc = await db.goal_tracks.find_one({"user_id": user.id})
    if doc:
        return doc
    seed = _progress_doc(user)
    await db.goal_tracks.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {**seed, "_id": ObjectId()}},
        upsert=True,
    )
    return await db.goal_tracks.find_one({"user_id": user.id}) or seed


def _to_progress_response(user: User, doc: Dict[str, Any]) -> UserTrackProgressResponse:
    track_id = doc.get("active_track_id")
    checked = list(doc.get("checked_item_ids") or [])
    track = get_track(track_id) if track_id else None
    level_id, level_name, level_index, level_count, pct_overall, pct_in_level = compute_progress(
        track, checked
    )
    return UserTrackProgressResponse(
        user_id=_uid_str(user),
        active_track_id=track_id,
        checked_item_ids=checked,
        level_id=level_id,
        level_name=level_name,
        level_index=level_index,
        level_count=level_count,
        pct_overall=pct_overall,
        pct_in_level=pct_in_level,
        updated_at=doc.get("updated_at"),
    )


def _find_item_track(item_id: str) -> Optional[str]:
    """Return track id that owns ``item_id``, if any."""
    for track in load_tracks().values():
        for lvl in track.levels:
            for it in lvl.items:
                if it.id == item_id:
                    return track.id
    return None


@router.get("/journey/tracks", response_model=List[Track])
async def list_journey_tracks(
    current_user: User = Depends(get_current_active_user),
) -> List[Track]:
    """List all track definitions (full levels + items)."""
    _ = current_user
    return list(load_tracks().values())


@router.get("/journey/tracks/summary", response_model=List[TrackSummary])
async def list_journey_track_summaries(
    current_user: User = Depends(get_current_active_user),
) -> List[TrackSummary]:
    _ = current_user
    return list_track_summaries()


@router.get("/journey/me", response_model=UserTrackProgressResponse)
async def get_my_journey(
    current_user: User = Depends(get_current_active_user),
) -> UserTrackProgressResponse:
    doc = await _get_or_create_progress(current_user)
    return _to_progress_response(current_user, doc)


@router.put("/journey/me", response_model=UserTrackProgressResponse)
async def update_my_journey(
    updates: UserTrackProgressUpdate,
    current_user: User = Depends(get_current_active_user),
) -> UserTrackProgressResponse:
    db = get_database()
    await _get_or_create_progress(current_user)

    set_fields: Dict[str, Any] = {"updated_at": datetime.utcnow()}

    if updates.active_track_id is not None:
        if updates.active_track_id == "":
            set_fields["active_track_id"] = None
        else:
            if not get_track(updates.active_track_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown track: {updates.active_track_id}",
                )
            set_fields["active_track_id"] = updates.active_track_id

    if updates.checked_item_ids is not None:
        # Deduplicate while preserving order
        seen = set()
        ordered: List[str] = []
        for iid in updates.checked_item_ids:
            if iid not in seen:
                seen.add(iid)
                ordered.append(iid)
        set_fields["checked_item_ids"] = ordered

    await db.goal_tracks.update_one(
        {"user_id": current_user.id},
        {"$set": set_fields},
    )
    doc = await db.goal_tracks.find_one({"user_id": current_user.id}) or _progress_doc(current_user)
    return _to_progress_response(current_user, doc)


@router.post("/journey/me/items/{item_id}/complete", response_model=UserTrackProgressResponse)
async def complete_journey_item(
    item_id: str,
    current_user: User = Depends(get_current_active_user),
) -> UserTrackProgressResponse:
    if not _find_item_track(item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown item")

    db = get_database()
    doc = await _get_or_create_progress(current_user)
    checked = list(doc.get("checked_item_ids") or [])
    if item_id not in checked:
        checked.append(item_id)

    # Auto-set active track from the item if none selected
    active = doc.get("active_track_id")
    owner_track = _find_item_track(item_id)
    if not active and owner_track:
        active = owner_track

    await db.goal_tracks.update_one(
        {"user_id": current_user.id},
        {
            "$set": {
                "checked_item_ids": checked,
                "active_track_id": active,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    doc = await db.goal_tracks.find_one({"user_id": current_user.id}) or doc
    return _to_progress_response(current_user, doc)


@router.post("/journey/me/items/{item_id}/uncomplete", response_model=UserTrackProgressResponse)
async def uncomplete_journey_item(
    item_id: str,
    current_user: User = Depends(get_current_active_user),
) -> UserTrackProgressResponse:
    db = get_database()
    doc = await _get_or_create_progress(current_user)
    checked = [iid for iid in (doc.get("checked_item_ids") or []) if iid != item_id]
    await db.goal_tracks.update_one(
        {"user_id": current_user.id},
        {"$set": {"checked_item_ids": checked, "updated_at": datetime.utcnow()}},
    )
    doc = await db.goal_tracks.find_one({"user_id": current_user.id}) or doc
    return _to_progress_response(current_user, doc)


@router.post("/journey/me/assessments", response_model=AssessmentResponse)
async def create_assessment(
    body: AssessmentCreate,
    current_user: User = Depends(get_current_active_user),
) -> AssessmentResponse:
    db = get_database()
    progress = await _get_or_create_progress(current_user)
    track_id = body.track_id or progress.get("active_track_id")
    if track_id and not get_track(track_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown track")

    assessment_id = ObjectId()
    created_at = datetime.utcnow()
    doc = {
        "_id": assessment_id,
        "user_id": current_user.id,
        "track_id": track_id,
        "scores": body.scores or {},
        "notes": body.notes,
        "created_at": created_at,
    }
    await db.assessments.insert_one(doc)
    return AssessmentResponse(
        id=str(assessment_id),
        user_id=_uid_str(current_user),
        track_id=track_id,
        scores=doc["scores"],
        notes=body.notes,
        created_at=created_at,
    )


@router.get("/journey/me/assessments", response_model=List[AssessmentResponse])
async def list_assessments(
    current_user: User = Depends(get_current_active_user),
) -> List[AssessmentResponse]:
    db = get_database()
    cursor = db.assessments.find({"user_id": current_user.id}).sort("created_at", -1)
    results: List[AssessmentResponse] = []
    async for doc in cursor:
        results.append(
            AssessmentResponse(
                id=str(doc.get("_id")),
                user_id=str(doc.get("user_id", current_user.id)),
                track_id=doc.get("track_id"),
                scores=doc.get("scores") or {},
                notes=doc.get("notes"),
                created_at=doc.get("created_at"),
            )
        )
    return results
