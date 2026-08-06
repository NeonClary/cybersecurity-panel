"""Pydantic models for the Security Journey track engine."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, Field

from app.models.user import PyObjectId

Audience = Literal["individual", "smb", "enterprise", "any"]


class TrackItem(BaseModel):
    id: str
    title: str
    description: str = ""


class TrackLevel(BaseModel):
    id: str
    name: str
    description: str = ""
    items: List[TrackItem] = []


class Track(BaseModel):
    id: str
    name: str
    description: str = ""
    audience: Audience = "any"
    levels: List[TrackLevel] = []


class TrackSummary(BaseModel):
    """Lightweight track listing (no nested item detail required by clients)."""

    id: str
    name: str
    description: str = ""
    audience: Audience = "any"
    level_count: int = 0
    item_count: int = 0


class UserTrackProgress(BaseModel):
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    active_track_id: Optional[str] = None
    checked_item_ids: List[str] = []
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserTrackProgressUpdate(BaseModel):
    active_track_id: Optional[str] = None
    checked_item_ids: Optional[List[str]] = None


class UserTrackProgressResponse(BaseModel):
    user_id: str
    active_track_id: Optional[str] = None
    checked_item_ids: List[str] = []
    level_id: Optional[str] = None
    level_name: Optional[str] = None
    level_index: int = 0
    level_count: int = 0
    pct_overall: float = 0.0
    pct_in_level: float = 0.0
    updated_at: Optional[datetime] = None


class Assessment(BaseModel):
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    track_id: Optional[str] = None
    scores: Dict[str, Any] = {}
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AssessmentCreate(BaseModel):
    scores: Dict[str, Any] = {}
    notes: Optional[str] = None
    track_id: Optional[str] = None


class AssessmentResponse(BaseModel):
    id: str
    user_id: str
    track_id: Optional[str] = None
    scores: Dict[str, Any] = {}
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
