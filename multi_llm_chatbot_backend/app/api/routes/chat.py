import asyncio
import json
import logging
import re
import time
import traceback
from typing import Any, Dict, List, Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.routes.chat_sessions import persist_message
from app.api.utils import get_or_create_session_for_request_async
from app.core.auth import get_current_active_user
from app.core.bootstrap import chat_orchestrator
from app.core.database import get_database
from app.core.session_manager import get_session_manager
from app.models.user import User
from app.api.routes.user_profile import PROFILE_FIELDS, enrich_profile_from_user
from app.core.advisor_stream import iter_parallel_advisor_events
from app.config import get_settings
from app.core import user_knowledge as uk
from app.core.user_context import extract_stated_goal
from app.core import bootstrap
from app.core.starter_suggestions import (
    fallback_starter_greeting,
    generate_starter_greeting,
    generate_starter_suggestions,
    iter_starter_suggestion_events,
)

logger = logging.getLogger(__name__)

router = APIRouter()
session_manager = get_session_manager()


async def _load_user_profile_context(user: User) -> str:
    """Load Mongo profile + knowledge summary as a prompt block."""
    db = get_database()
    doc = await db.user_profiles.find_one({"user_id": user.id})
    profile = enrich_profile_from_user(doc, user)
    parts = []
    for key in PROFILE_FIELDS:
        val = profile.get(key)
        if val:
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            parts.append(f"{key}: {val}")
    blocks = []
    if parts:
        blocks.append("USER SECURITY PROFILE: " + "; ".join(parts))
    try:
        summary = await uk.get_summary_for_provider(
            user.id,
            uk.is_small_context_provider(bootstrap.current_provider),
        )
        if summary:
            blocks.append("USER KNOWLEDGE SUMMARY: " + summary)
    except Exception as sum_err:
        logger.warning(f"Could not load user knowledge summary: {sum_err}")
    return "\n\n".join(blocks)


async def _attach_user_profile_context(session, user: User) -> None:
    """Load Mongo profile + knowledge summary into session for persona prompts."""
    try:
        context = await _load_user_profile_context(user)
        if context:
            session.user_profile_context = context
    except Exception as prof_err:
        logger.warning(f"Could not load user profile: {prof_err}")


def _schedule_fact_extraction(user_id, message_text: str) -> None:
    """Fire-and-forget inferred-fact extraction; never blocks the chat stream."""
    try:
        settings = get_settings()
        if not settings.user_knowledge.extract_on_every_message:
            return
    except Exception:
        return

    llm_client = chat_orchestrator.llm_client
    if llm_client is None:
        return

    async def _run():
        try:
            await uk.extract_facts_from_message(user_id, message_text, llm_client)
        except Exception as exc:
            logger.warning(f"Background fact extraction failed: {exc}")

    try:
        asyncio.create_task(_run())
    except RuntimeError as exc:
        logger.warning(f"Could not schedule fact extraction: {exc}")


# Enhanced data models
class UserInput(BaseModel):
    user_input: str

class ChatMessage(BaseModel):
    user_input: str
    session_id: Optional[str] = None
    chat_session_id: Optional[str] = None  # MongoDB chat session ID
    response_length: str = "medium"
    active_advisors: Optional[List[str]] = None
    prefetch: bool = False


def prefetch_session_id(user_id: Any) -> str:
    return f"prefetch_{user_id}"


def _orchestrator_llm():
    llm = chat_orchestrator.llm_client
    if llm is None and chat_orchestrator.personas:
        llm = next(iter(chat_orchestrator.personas.values())).llm
    return llm

class ReplyToAdvisor(BaseModel):
    user_input: str
    advisor_id: str
    original_message_id: str = None
    chat_session_id: Optional[str] = None

class PersonaQuery(BaseModel):
    question: str
    persona: str

class SwitchChatRequest(BaseModel):
    chat_session_id: str

class NewChatRequest(BaseModel):
    title: Optional[str] = "New Chat"

class StarterSuggestionItem(BaseModel):
    lead: str = ""
    question: str = ""
    chat_prompt: str = ""


class StarterSuggestionsRequest(BaseModel):
    count: int = Field(2, ge=1, le=12)
    exclude: List[str] = Field(default_factory=list)
    category_titles: List[str] = Field(default_factory=list)
    slot_index: Optional[int] = Field(None, ge=0, le=11)
    prompt_variation: Optional[int] = Field(None, ge=0, le=11)


class StarterSuggestionsResponse(BaseModel):
    suggestions: List[StarterSuggestionItem] = Field(default_factory=list)


class StarterGreetingResponse(BaseModel):
    greeting: str
    subheader: str
    cached: bool = False

ChatStreamEventType = Literal[
    "error", "progress", "clarification", "advisor",
    "advisor_start", "advisor_delta", "advisor_done", "followups",
]


class ChatStreamLine(BaseModel):
    """One NDJSON line from ``/chat-stream``."""

    type: ChatStreamEventType
    data: Dict[str, Any] = Field(default_factory=dict)

    def to_ndjson(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False) + "\n"


@router.post("/chat-stream")
async def chat_stream(
    message: ChatMessage,
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """
    Streaming chat endpoint (newline-delimited JSON).
    @param message: ChatMessage containing user input and optional session/chat IDs
    @param request: FastAPI Request object for session management
    @param current_user: Authenticated user from dependency injection
    @return: StreamingResponse that yields ChatStreamLine events as NDJSON
    """

    async def _event_generator():
        try:
            prefetch = bool(message.prefetch)
            # Load or create the in-memory session
            if prefetch:
                sid = prefetch_session_id(current_user.id)
                session = session_manager.get_session(sid)
                session.clear_messages()
            elif message.chat_session_id:
                sid = f"chat_{message.chat_session_id}"
                existing = session_manager.sessions.get(sid)
                needs_history = existing is None or not any(
                    (m.get("role") == "user" and str(m.get("content") or "").strip())
                    for m in (getattr(existing, "messages", None) or [])
                )
                if needs_history:
                    sid = await get_or_create_session_for_request_async(
                        request,
                        chat_session_id=message.chat_session_id,
                        user_id=str(current_user.id),
                    )
                session = session_manager.get_session(sid)
            else:
                sid = await get_or_create_session_for_request_async(request)
                session = session_manager.get_session(sid)

            t0 = time.perf_counter()

            def _elapsed() -> str:
                return f"{time.perf_counter() - t0:.2f}s"

            await _attach_user_profile_context(session, current_user)
            await chat_orchestrator.attach_datetime_context(session)
            logger.info("chat-stream profile+datetime ready in %s", _elapsed())

            # Append user message to in-memory session and persist to MongoDB
            session.append_message("user", message.user_input)
            if not prefetch:
                _schedule_fact_extraction(current_user.id, message.user_input)
            if message.chat_session_id and not prefetch:
                async def _persist_user():
                    try:
                        await persist_message(message.chat_session_id, {
                            "id": str(ObjectId()),
                            "type": "user",
                            "content": message.user_input,
                        })
                    except Exception as persist_err:
                        logger.warning("Background user persist failed: %s", persist_err)

                try:
                    asyncio.create_task(_persist_user())
                except RuntimeError as persist_err:
                    logger.warning("Could not schedule user persist: %s", persist_err)

            user_ctx = getattr(session, "user_profile_context", "") or ""
            if await chat_orchestrator.needs_clarification_improved(
                session, message.user_input, user_ctx
            ):
                logger.info("chat-stream clarification needed after %s", _elapsed())
                clar = await chat_orchestrator.generate_contextual_clarification(
                    message.user_input, user_ctx, session=session
                )
                yield ChatStreamLine(
                    type="clarification",
                    data={
                        "message": clar["question"],
                        "suggestions": clar["suggestions"],
                    },
                ).to_ndjson()
                yield ChatStreamLine(
                    type="progress",
                    data={"phase": "complete"},
                ).to_ndjson()
                return

            # If an enabled tool can handle this query, return its response
            # directly and skip persona generation.
            tool_result = await chat_orchestrator.get_tool_response(message.user_input)
            if tool_result.used_tool:
                session.append_message("orchestrator", tool_result.text)
                yield ChatStreamLine(
                    type="advisor",
                    data={
                        "persona_id": "orchestrator",
                        "persona_name": "Orchestrator",
                        "content": tool_result.text,
                        "used_documents": False,
                        "document_chunks_used": 0,
                    },
                ).to_ndjson()
                yield ChatStreamLine(
                    type="progress",
                    data={"phase": "complete"},
                ).to_ndjson()
                return

            # Route in one LLM call: urgency classification + profile-aware
            # ranking, scoped to the user's active-advisor selection when one
            # is provided. Jerry (the required lead) is always included; in
            # triage mode the incident expert responds first.
            if message.active_advisors:
                candidate_ids = [
                    pid for pid in message.active_advisors
                    if pid in chat_orchestrator.personas
                ]
            else:
                candidate_ids = list(chat_orchestrator.personas.keys())
            routing = await chat_orchestrator.route_message(
                session_id=sid,
                user_input=message.user_input,
                k=3,
                candidate_ids=candidate_ids,
            )
            top_personas = routing["advisors"]
            urgency = routing["urgency"]
            logger.info(
                "chat-stream routed urgency=%s advisors=%s in %s",
                urgency, top_personas, _elapsed(),
            )

            # Triage short-circuit (plan §5.5): personas lead with immediate
            # first steps instead of profiling questions.
            if urgency == "triage":
                session.urgency_context = (
                    "ACTIVE INCIDENT TRIAGE: The user may be dealing with an "
                    "active security incident right now. Lead with calm, "
                    "concrete first steps they should take immediately. Do "
                    "not ask profiling questions first; at most one short "
                    "clarifying question at the end."
                )
            else:
                session.urgency_context = ""

            # Tell the client which advisors will respond so it can show
            # thinking indicators for just those, not the entire active pool.
            yield ChatStreamLine(
                type="progress",
                data={
                    "phase": "selected",
                    "selected_advisors": top_personas,
                    "urgency": urgency,
                },
            ).to_ndjson()

            persona_timeout = float(
                get_settings().orchestrator.persona_response_timeout_seconds
            )

            def _persona_meta(pid: str) -> Dict[str, str]:
                persona = chat_orchestrator.get_persona(pid)
                return {
                    "persona_name": persona.name if persona else pid,
                }

            async def _stream_one(pid: str):
                persona = chat_orchestrator.get_persona(pid)
                if persona is None:
                    yield {
                        "event": "done",
                        "result": {
                            "persona_id": pid,
                            "persona_name": pid,
                            "response": "This advisor is unavailable.",
                            "used_documents": False,
                            "document_chunks_used": 0,
                        },
                    }
                    return
                async for item in chat_orchestrator.iter_persona_response_stream(
                    session, persona, message.response_length or "medium",
                ):
                    yield item

            async def _on_complete(_pid: str, result: Dict[str, Any]) -> None:
                session.append_message(_pid, result.get("response", ""))

            first_advisor = True
            async for event in iter_parallel_advisor_events(
                top_personas,
                _stream_one,
                persona_timeout,
                _persona_meta,
                on_complete=_on_complete,
            ):
                if first_advisor and event.get("type") == "advisor_start":
                    logger.info(
                        "chat-stream first advisor %s in %s",
                        event.get("data", {}).get("persona_id"),
                        _elapsed(),
                    )
                    first_advisor = False
                yield ChatStreamLine(
                    type=event["type"],
                    data=event.get("data") or {},
                ).to_ndjson()

            logger.info("chat-stream all advisors done in %s", _elapsed())

            yield ChatStreamLine(
                type="progress",
                data={"phase": "complete"},
            ).to_ndjson()

            if not prefetch:
                # Follow-up chips after complete so the UI can unlock input
                # without waiting on this extra LLM call.
                try:
                    followups = await chat_orchestrator.generate_followups(sid)
                except Exception as fu_err:
                    logger.warning(f"Follow-up generation errored: {fu_err}")
                    followups = []
                if followups:
                    yield ChatStreamLine(
                        type="followups",
                        data={"suggestions": followups},
                    ).to_ndjson()

                if uk.should_regenerate_after_chat(
                    len([m for m in session.messages if m.get("role") == "user"])
                ):
                    uk.schedule_summary_regeneration(current_user.id)

            logger.info("chat-stream finished in %s", _elapsed())

        except Exception as exc:
            logger.error(f"chat-stream error: {exc}")
            logger.error(traceback.format_exc())
            yield ChatStreamLine(
                type="error",
                data={"detail": str(exc)},
            ).to_ndjson()

    return StreamingResponse(
        _event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/switch-chat")
async def switch_to_chat(
    request: SwitchChatRequest, 
    req: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Switch to an existing chat session and load its context - FIXED VERSION
    Ensures documents are accessible after switching
    """
    try:
        logger.info(f"Switching to chat session: {request.chat_session_id}")
        
        # Load the chat session into memory context with consistent session ID
        memory_session_id = await get_or_create_session_for_request_async(
            req, 
            chat_session_id=request.chat_session_id,
            user_id=str(current_user.id)
        )
        
        if not memory_session_id:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        logger.info(f"Loaded chat into memory session: {memory_session_id}")
        
        # Get the loaded session
        session = session_manager.get_session(memory_session_id)
        
        # Verify document access after loading
        rag_stats = session.get_rag_stats()
        logger.info(f"After switch - Session {memory_session_id} has {rag_stats.get('total_documents', 0)} documents")
        
        # Get the original MongoDB chat session to retrieve messages in proper format
        db = get_database()
        chat_session = await db.chat_sessions.find_one({
            "_id": ObjectId(request.chat_session_id),
            "user_id": current_user.id,
            "is_active": True
        })
        
        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found in database")
        
        # Return the messages in the original frontend format from MongoDB
        original_messages = chat_session.get("messages", [])
        
        logger.info(f"Switch successful - {len(original_messages)} messages, {rag_stats.get('total_documents', 0)} documents")
        
        return {
            "status": "success",
            "memory_session_id": memory_session_id,
            "chat_session_id": request.chat_session_id,
            "message_count": len(original_messages),
            "context": {
                "messages": original_messages,  # Return original format messages
                "rag_info": rag_stats
            },
            # Include document access verification
            "document_access": {
                "total_documents": rag_stats.get('total_documents', 0),
                "total_chunks": rag_stats.get('total_chunks', 0),
                "documents": rag_stats.get('documents', []),
                "uploaded_files": session.uploaded_files
            },
            "debug_info": {
                "memory_session_format": memory_session_id,
                "documents_accessible": rag_stats.get('total_documents', 0) > 0,
                "session_loaded": memory_session_id in session_manager.sessions
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching to chat {request.chat_session_id}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to switch to chat")

@router.post("/new-chat")
async def create_new_chat(
    request: NewChatRequest,
    req: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new chat with fresh context
    """
    try:
        # Create a completely new session (no chat_session_id means fresh context)
        memory_session_id = await get_or_create_session_for_request_async(req)
        
        # Ensure the session is completely clean
        session = session_manager.get_session(memory_session_id)
        session.clear_all_data()  # This clears both messages and documents
        
        return {
            "status": "success",
            "memory_session_id": memory_session_id,
            "message": "New chat created with fresh context",
            "context": {
                "messages": [],
                "rag_info": {"total_documents": 0, "total_chunks": 0}
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating new chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to create new chat")

@router.post("/chat/starter-suggestions", response_model=StarterSuggestionsResponse)
async def starter_suggestions(
    body: StarterSuggestionsRequest,
    current_user: User = Depends(get_current_active_user),
) -> StarterSuggestionsResponse:
    """Generate one Getting Started chip per category, grounded in the user's goal."""
    try:
        user_context = await _load_user_profile_context(current_user)
        llm = _orchestrator_llm()
        titles = [t.strip() for t in (body.category_titles or []) if isinstance(t, str) and t.strip()]
        n = len(titles) if titles else body.count
        n = max(1, min(int(n), 12))
        variation = body.prompt_variation
        if variation is None and body.slot_index is not None:
            variation = int(body.slot_index)
        suggestions = await generate_starter_suggestions(
            llm,
            user_context,
            count=n,
            exclude=body.exclude or [],
            category_titles=titles,
            prompt_variation=variation,
        )
        return StarterSuggestionsResponse(
            suggestions=[StarterSuggestionItem(**item) for item in suggestions],
        )
    except Exception as exc:
        logger.warning("Starter suggestion endpoint failed: %s", exc)
        return StarterSuggestionsResponse(suggestions=[])


@router.post("/chat/starter-greeting", response_model=StarterGreetingResponse)
async def starter_greeting(
    current_user: User = Depends(get_current_active_user),
) -> StarterGreetingResponse:
    """Goal-specific starter greeting + subheader (orchestrator model)."""
    user_context = ""
    try:
        user_context = await _load_user_profile_context(current_user)
    except Exception as exc:
        logger.warning("Starter greeting context failed: %s", exc)
    fallback = fallback_starter_greeting(extract_stated_goal(user_context))
    try:
        llm = _orchestrator_llm()
        result = await asyncio.wait_for(
            generate_starter_greeting(llm, user_context),
            timeout=5.0,
        )
        return StarterGreetingResponse(
            greeting=result.get("greeting") or fallback["greeting"],
            subheader=result.get("subheader") or fallback["subheader"],
        )
    except Exception as exc:
        logger.warning("Starter greeting endpoint failed: %s", exc)
        return StarterGreetingResponse(
            greeting=fallback["greeting"],
            subheader=fallback["subheader"],
        )


@router.post("/chat/starter-suggestions-stream")
async def starter_suggestions_stream(
    body: StarterSuggestionsRequest,
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """Stream Getting Started chips token-by-token into stable slots 0..n."""

    async def _event_generator():
        try:
            user_context = await _load_user_profile_context(current_user)
            llm = _orchestrator_llm()
            titles = [
                t.strip() for t in (body.category_titles or [])
                if isinstance(t, str) and t.strip()
            ]
            if not titles:
                titles = [f"Starter {i + 1}" for i in range(max(1, min(int(body.count or 1), 12)))]
            async for event in iter_starter_suggestion_events(
                llm,
                user_context,
                category_titles=titles[:12],
                exclude=body.exclude or [],
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            logger.warning("Starter suggestion stream failed: %s", exc)
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"

    return StreamingResponse(
        _event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/{persona_id}")
async def chat_with_specific_advisor(persona_id: str, input: UserInput, request: Request):
    """Chat with a specific advisor - UPDATED"""
    try:
        if persona_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

        # Use async session management
        session_id = await get_or_create_session_for_request_async(request)
        
        result = await chat_orchestrator.chat_with_persona(
            user_input=input.user_input,
            persona_id=persona_id,
            session_id=session_id
        )
        
        # Handle response structure
        if result.get("type") == "single_persona_response" and "persona" in result:
            persona_data = result["persona"]
            return {
                "persona": persona_data["persona_name"],
                "persona_id": persona_data["persona_id"],
                "response": persona_data["response"]
            }
        elif "persona_id" in result and "response" in result:
            return {
                "persona": result["persona_name"],
                "persona_id": result["persona_id"],
                "response": result["response"]
            }
        else:
            return {
                "persona": "System",
                "response": "I'm having trouble generating a response right now. Please try again."
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat_with_specific_advisor: {e}")
        return {
            "persona": "System",
            "response": "I'm having trouble generating a response right now. Please try again."
        }

@router.post("/reply-to-advisor")
async def reply_to_advisor(reply: ReplyToAdvisor, request: Request):
    """Reply to a specific advisor with proper context - UPDATED"""
    try:
        if reply.advisor_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Advisor '{reply.advisor_id}' not found")

        # Handle session management for existing chats
        if reply.chat_session_id:
            session_id = f"chat_{reply.chat_session_id}"
        else:
            session_id = await get_or_create_session_for_request_async(request)
        
        session = session_manager.get_session(session_id)
        
        # Find the original message being replied to for context
        original_message = None
        if reply.original_message_id:
            for msg in session.messages:
                if getattr(msg, 'id', None) == reply.original_message_id:
                    original_message = msg.content
                    break
        
        # Create context-aware input
        contextual_input = reply.user_input
        if original_message:
            contextual_input = f"[Replying to your previous message: '{original_message[:100]}...'] {reply.user_input}"
        
        result = await chat_orchestrator.chat_with_persona(
            user_input=contextual_input,
            persona_id=reply.advisor_id,
            session_id=session_id
        )
        
        # Handle response structure
        if result.get("type") == "single_persona_response" and "persona" in result:
            persona_data = result["persona"]
            return {
                "type": "advisor_reply",
                "persona": persona_data["persona_name"],
                "persona_id": persona_data["persona_id"],
                "response": persona_data["response"],
                "original_message_id": reply.original_message_id
            }
        elif "persona_id" in result and "response" in result:
            return {
                "type": "advisor_reply",
                "persona": result["persona_name"],
                "persona_id": result["persona_id"],
                "response": result["response"],
                "original_message_id": reply.original_message_id
            }
        else:
            return {
                "type": "error",
                "persona": "System",
                "response": "I'm having trouble generating a reply right now. Please try again."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reply_to_advisor: {e}")
        return {
            "type": "error",
            "persona": "System",
            "response": "I'm having trouble generating a reply right now. Please try again."
        }

@router.post("/ask/")
async def ask_question(query: PersonaQuery, request: Request):
    """Ask question - UPDATED"""
    try:
        session_id = await get_or_create_session_for_request_async(request)
        
        result = await chat_orchestrator.chat_with_persona(
            user_input=query.question,
            persona_id=query.persona,
            session_id=session_id
        )
        
        if result["type"] == "single_persona_response":
            response_text = result["persona"]["response"]
        else:
            response_text = result.get("message", "I'm having trouble responding right now.")
        
        return {"response": response_text}
        
    except Exception as e:
        logger.error(f"Error in ask endpoint: {str(e)}")
        return {"response": "I encountered an error. Please try again."}
