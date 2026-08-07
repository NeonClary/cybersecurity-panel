from datetime import datetime
from typing import List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, Field

from app.models.user import PyObjectId

FactCategory = Literal["person", "organization", "environment", "needs", "preferences"]
FactSource = Literal["stated", "inferred"]


class UserFact(BaseModel):
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    category: FactCategory
    key: str
    value: str
    source: FactSource
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserFactCreate(BaseModel):
    category: FactCategory
    key: str
    value: str
    evidence: Optional[str] = None


class UserFactUpdate(BaseModel):
    value: Optional[str] = None
    source: Optional[FactSource] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    category: Optional[FactCategory] = None


class UserFactResponse(BaseModel):
    id: str
    user_id: str
    category: FactCategory
    key: str
    value: str
    source: FactSource
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserFactListResponse(BaseModel):
    facts: List[UserFactResponse]


class UserSummary(BaseModel):
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    short: str = ""
    long: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[int] = None


class UserSummaryResponse(BaseModel):
    user_id: str
    short: str = ""
    long: str = ""
    generated_at: Optional[datetime] = None
    version: Optional[int] = None
