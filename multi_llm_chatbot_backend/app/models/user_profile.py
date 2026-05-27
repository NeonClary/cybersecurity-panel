from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field

from app.models.user import PyObjectId


class UserProfile(BaseModel):
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    knowledge_level: Optional[str] = None
    timezone: Optional[str] = None
    cyber_role: Optional[str] = None
    organization_type: Optional[str] = None
    primary_domains: List[str] = []
    certifications: List[str] = []
    tools_stack: List[str] = []
    compliance_focus: Optional[str] = None
    current_goals: Optional[str] = None
    learning_preferences: Optional[str] = None
    advisor_notes: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfileUpdate(BaseModel):
    knowledge_level: Optional[str] = None
    timezone: Optional[str] = None
    cyber_role: Optional[str] = None
    organization_type: Optional[str] = None
    primary_domains: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    tools_stack: Optional[List[str]] = None
    compliance_focus: Optional[str] = None
    current_goals: Optional[str] = None
    learning_preferences: Optional[str] = None
    advisor_notes: Optional[str] = None


class UserProfileResponse(BaseModel):
    user_id: str
    knowledge_level: Optional[str] = None
    timezone: Optional[str] = None
    cyber_role: Optional[str] = None
    organization_type: Optional[str] = None
    primary_domains: List[str] = []
    certifications: List[str] = []
    tools_stack: List[str] = []
    compliance_focus: Optional[str] = None
    current_goals: Optional[str] = None
    learning_preferences: Optional[str] = None
    advisor_notes: Optional[str] = None
    updated_at: Optional[datetime] = None
    completion_pct: int = 0
