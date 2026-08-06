"""HTTP routes for user facts and dual summaries."""

import logging
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_active_user
from app.core.bootstrap import create_llm_client
from app.core import user_knowledge as uk
from app.models.user import User
from app.models.user_knowledge import (
    UserFactCreate,
    UserFactListResponse,
    UserFactResponse,
    UserFactUpdate,
    UserSummaryResponse,
)

LOG = logging.getLogger(__name__)

router = APIRouter()


def _fact_response(doc: dict) -> UserFactResponse:
    return UserFactResponse(
        id=str(doc.get("_id") or doc.get("id")),
        user_id=str(doc.get("user_id")),
        category=doc["category"],
        key=doc["key"],
        value=doc["value"],
        source=doc["source"],
        confidence=doc.get("confidence"),
        evidence=doc.get("evidence"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.get("/users/me/facts", response_model=UserFactListResponse)
async def list_my_facts(
    source: Optional[str] = Query(None, description="Filter: stated | inferred"),
    current_user: User = Depends(get_current_active_user),
) -> UserFactListResponse:
    if source is not None and source not in ("stated", "inferred"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source must be 'stated' or 'inferred'",
        )
    docs = await uk.list_facts(current_user.id, source=source)
    return UserFactListResponse(facts=[_fact_response(d) for d in docs])


@router.post("/users/me/facts", response_model=UserFactResponse, status_code=status.HTTP_201_CREATED)
async def create_my_fact(
    body: UserFactCreate,
    current_user: User = Depends(get_current_active_user),
) -> UserFactResponse:
    if not body.key.strip() or not body.value.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="key and value are required",
        )
    doc = await uk.create_stated_fact(
        current_user.id,
        category=body.category,
        key=body.key,
        value=body.value,
        evidence=body.evidence,
    )
    return _fact_response(doc)


@router.put("/users/me/facts/{fact_id}", response_model=UserFactResponse)
async def update_my_fact(
    fact_id: str,
    body: UserFactUpdate,
    current_user: User = Depends(get_current_active_user),
) -> UserFactResponse:
    try:
        ObjectId(fact_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid fact id")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    doc = await uk.update_fact(current_user.id, fact_id, updates)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")
    return _fact_response(doc)


@router.delete("/users/me/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_fact(
    fact_id: str,
    current_user: User = Depends(get_current_active_user),
) -> None:
    try:
        ObjectId(fact_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid fact id")
    deleted = await uk.delete_fact(current_user.id, fact_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")


@router.get("/users/me/summaries", response_model=UserSummaryResponse)
async def get_my_summaries(
    current_user: User = Depends(get_current_active_user),
) -> UserSummaryResponse:
    doc = await uk.get_summaries_doc(current_user.id)
    if not doc:
        return UserSummaryResponse(user_id=str(current_user.id), short="", long="")
    return UserSummaryResponse(
        user_id=str(current_user.id),
        short=doc.get("short") or "",
        long=doc.get("long") or "",
        generated_at=doc.get("generated_at"),
        version=doc.get("version"),
    )


@router.post("/users/me/summaries/regenerate", response_model=UserSummaryResponse)
async def regenerate_my_summaries(
    current_user: User = Depends(get_current_active_user),
) -> UserSummaryResponse:
    llm = create_llm_client()
    doc = await uk.regenerate_summaries(current_user.id, llm)
    return UserSummaryResponse(
        user_id=str(current_user.id),
        short=doc.get("short") or "",
        long=doc.get("long") or "",
        generated_at=doc.get("generated_at"),
        version=doc.get("version"),
    )
