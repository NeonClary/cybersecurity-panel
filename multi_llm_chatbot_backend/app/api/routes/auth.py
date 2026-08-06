from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, timedelta
from app.models.user import UserCreate, UserLogin, User, Token, UserResponse, UserUpdate
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Literal
from uuid import uuid4
from app.core.auth import (
    get_password_hash, 
    verify_password,
    authenticate_user, 
    create_access_token, 
    get_user_by_email,
    get_current_active_user,
    create_user_response,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.core.database import get_database
from app.core.guest_demo import resolve_persona, seed_guest_demo, clear_guest_sample_data
from app.core import user_knowledge
import logging
import secrets

logger = logging.getLogger(__name__)


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @model_validator(mode="after")
    def passwords_must_differ(self):
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current password")
        return self


class DeleteAccountRequest(BaseModel):
    password: str = ""


class GuestExploreRequest(BaseModel):
    """Intake for Explore as guest — two preset paths or free text."""
    choice: Literal["personal", "business", "other"] = "personal"
    free_text: Optional[str] = Field(default=None, max_length=800)


class ClearSampleResponse(BaseModel):
    message: str
    cleared: List[str]


router = APIRouter()

@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate):
    """
    Register a new user and return an access token.
    @param user_data: UserCreate with name, email, password, and optional academic fields
    @return: Token containing a JWT access token and the created UserResponse
    """
    try:
        db = get_database()
        
        # Check if user already exists
        existing_user = await get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        user = User(
            firstName=user_data.firstName,
            lastName=user_data.lastName,
            email=user_data.email,
            hashed_password=hashed_password,
            academicStage=user_data.academicStage,
            researchArea=user_data.researchArea,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        # Insert user into database
        result = await db.users.insert_one(user.dict(by_alias=True))
        user.id = result.inserted_id

        profile_seed: dict = {
            "user_id": user.id,
            "updated_at": datetime.utcnow(),
        }
        if user_data.academicStage:
            profile_seed["knowledge_level"] = user_data.academicStage
        if user_data.researchArea:
            profile_seed["timezone"] = user_data.researchArea
        await db.user_profiles.update_one(
            {"user_id": user.id},
            {"$set": profile_seed},
            upsert=True,
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, 
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=create_user_response(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create user account"
        )

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """
    Authenticate a user and return an access token.
    @param user_credentials: UserLogin with email and password
    @return: Token containing a JWT access token and the authenticated UserResponse
    """
    try:
        # Authenticate user
        user = await authenticate_user(user_credentials.email, user_credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last login time
        db = get_database()
        await db.users.update_one(
            {"_id": user.id},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        user.last_login = datetime.utcnow()

        # Session-start trigger: refresh the dual user summaries (plan §4.2).
        user_knowledge.schedule_summary_regeneration(user.id)

        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, 
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=create_user_response(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    """
    Retrieve the profile of the currently authenticated user.
    @param current_user: Authenticated user from dependency injection
    @return: UserResponse with the user's profile information
    """
    return create_user_response(current_user)

@router.post("/logout", response_model=MessageResponse)
async def logout():
    """
    Log out the current user (client should discard the token).
    @return: MessageResponse with a confirmation message
    """
    return MessageResponse(message="Successfully logged out")

@router.post("/verify-token", response_model=UserResponse)
async def verify_token(current_user: User = Depends(get_current_active_user)):
    """
    Validate the caller's JWT and return their profile.
    @param current_user: Authenticated user from dependency injection
    @return: UserResponse with the user's profile information
    """
    return create_user_response(current_user)

@router.post("/me/password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Change the authenticated user's password.
    @param body: ChangePasswordRequest with the current and new passwords
    @param current_user: Authenticated user from dependency injection
    @return: MessageResponse with a confirmation message
    """
    try:
        if not verify_password(body.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        if len(body.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters",
            )
        db = get_database()
        await db.users.update_one(
            {"_id": current_user.id},
            {"$set": {"hashed_password": get_password_hash(body.new_password)}},
        )
        return MessageResponse(message="Password changed successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during password change: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not change password"
        )

@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UserUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update account fields (name, email, avatar, signup preferences)."""
    try:
        db = get_database()
        updates = {k: v for k, v in body.dict().items() if v is not None}
        if body.firstName is not None:
            updates["firstName"] = body.firstName.strip()
        if body.lastName is not None:
            updates["lastName"] = body.lastName.strip()
        if not updates:
            return create_user_response(current_user)

        if "email" in updates and updates["email"] != current_user.email:
            existing = await get_user_by_email(updates["email"])
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )

        await db.users.update_one({"_id": current_user.id}, {"$set": updates})
        profile_sync: dict = {"updated_at": datetime.utcnow()}
        if body.academicStage is not None:
            profile_sync["knowledge_level"] = body.academicStage
        if body.researchArea is not None:
            profile_sync["timezone"] = body.researchArea
        if len(profile_sync) > 1:
            await db.user_profiles.update_one(
                {"user_id": current_user.id},
                {"$set": profile_sync, "$setOnInsert": {"user_id": current_user.id}},
                upsert=True,
            )
        updated_user = await db.users.find_one({"_id": current_user.id})
        return create_user_response(User(**updated_user))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during profile update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update profile"
        )

@router.delete("/me", response_model=MessageResponse)
async def delete_account(
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Permanently delete the authenticated user's account, chat sessions, canvas,
    profile, onboarding, user facts, and user summaries.
    @param body: DeleteAccountRequest with the user's password for confirmation
    @param current_user: Authenticated user from dependency injection
    @return: MessageResponse with a confirmation message
    """
    try:
        is_guest = bool(getattr(current_user, "is_guest", False))
        if not is_guest:
            if not body.password or not verify_password(body.password, current_user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect password",
                )
        db = get_database()
        uid = current_user.id

        # Purge uploaded-document chunks (ChromaDB) for each of the user's
        # chats before the chat sessions themselves are removed.
        try:
            from app.core.rag_manager import get_rag_manager
            rag = get_rag_manager()
            sessions = await db.chat_sessions.find(
                {"user_id": uid}
            ).to_list(length=1000)
            for s in sessions:
                rag.delete_session_documents(f"chat_{s['_id']}")
        except Exception as rag_err:
            logger.warning(f"RAG purge during account deletion failed: {rag_err}")

        await db.chat_sessions.delete_many({"user_id": uid})
        await db.phd_canvases.delete_many({"user_id": uid})
        await db.user_profiles.delete_many({"user_id": uid})
        await db.onboarding_conversations.delete_many({"user_id": uid})
        await db.user_facts.delete_many({"user_id": uid})
        await db.user_summaries.delete_many({"user_id": uid})
        await db.goal_tracks.delete_many({"user_id": uid})
        await db.assessments.delete_many({"user_id": uid})
        await db.users.delete_one({"_id": uid})
        return MessageResponse(message="Account deleted")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during account deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete account"
        )


@router.post("/guest", response_model=Token)
async def explore_as_guest(body: GuestExploreRequest):
    """Create a temporary guest user, seed demo data from intake, return JWT."""
    try:
        if body.choice == "other" and not (body.free_text or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please describe what you need help with",
            )

        persona = resolve_persona(body.choice, body.free_text)
        db = get_database()
        guest_id = uuid4().hex[:12]
        email = f"guest.{guest_id}@guest.neonai.dev"
        first = "Guest"
        last = {
            "personal": "Explorer",
            "business": "Advisor Demo",
            "other": "Explorer",
        }.get(persona, "Explorer")

        user = User(
            firstName=first,
            lastName=last,
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            academicStage="Beginner" if persona == "personal" else "Intermediate",
            researchArea="Guest demo",
            created_at=datetime.utcnow(),
            is_active=True,
            is_guest=True,
            guest_persona=persona,
        )
        result = await db.users.insert_one(user.dict(by_alias=True))
        user.id = result.inserted_id

        await seed_guest_demo(
            user.id,
            persona,
            free_text=(body.free_text or "").strip() or None,
        )

        # Session-start trigger: summarize the seeded demo facts so advisors
        # have user context from the first guest message.
        user_knowledge.schedule_summary_regeneration(user.id)

        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=create_user_response(user),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating guest session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start guest session",
        )


@router.post("/guest/clear-sample", response_model=ClearSampleResponse)
async def clear_guest_sample(
    current_user: User = Depends(get_current_active_user),
):
    """Remove all seeded demo data for the current guest (or any user requesting reset)."""
    try:
        cleared = await clear_guest_sample_data(current_user.id)
        return ClearSampleResponse(
            message="Sample data removed. You are still in guest mode with a clean slate.",
            cleared=cleared,
        )
    except Exception as e:
        logger.error(f"Error clearing guest sample data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not clear sample data",
        )