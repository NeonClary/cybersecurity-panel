from fastapi import APIRouter, Request, HTTPException, Body
from app.models.persona import Persona
from app.core.session_manager import get_session_manager
from app.api.utils import get_or_create_session_for_request
from app.core.bootstrap import chat_orchestrator
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

session_manager = get_session_manager()

# Keep all the same data models as before
class UserInput(BaseModel):
    user_input: str

class ChatMessage(BaseModel):
    user_input: str
    session_id: str = None
    response_length: str = "medium"

class ReplyToAdvisor(BaseModel):
    user_input: str
    advisor_id: str
    original_message_id: str = None

class PersonaQuery(BaseModel):
    question: str
    persona: str


@router.post("/chat-sequential")
async def chat_sequential_enhanced(message: ChatMessage, request: Request):
    """
    Enhanced sequential chat with orchestrator clarification for vague queries.
    """
    try:
        # Get or create session
        session_id = get_or_create_session_for_request(request, message.session_id)
        
        # STEP 1: Check if clarification is needed using orchestrator's logic
        session = session_manager.get_session(session_id)
        
        # Debug logging
        user_messages_count = len([msg for msg in session.messages if msg.get('role') == 'user'])
        logger.info(f"Session {session_id} has {user_messages_count} user messages before processing")
        logger.info(f"Input to analyze: '{message.user_input}'")
        
        # Check if this needs clarification BEFORE adding the message
        needs_clarification = chat_orchestrator._needs_clarification(session, message.user_input)
        
        logger.info(f"Clarification needed: {needs_clarification}")
        
        # Add user message to session for context (after clarification check)
        session.append_message("user", message.user_input)
        
        if needs_clarification:
            # Generate clarification question
            clarification_question = await chat_orchestrator._generate_clarification_question(session)
            
            logger.info(f"Clarification needed for session {session_id}: '{message.user_input}'")
            
            return {
                "type": "clarification_needed",
                "message": clarification_question,
                "suggestions": chat_orchestrator._get_clarification_suggestions(),
                "session_id": session_id
            }
        
        # STEP 2: No clarification needed - proceed with intelligent persona ordering
        # (user message already added to session above)
        
        # Get intelligently ordered personas based on context (TOP 3 ONLY)
        top_personas = await chat_orchestrator.get_top_personas(
            session_id=session_id, 
            k=3  # Limit to top 3 most relevant personas
        )
        
        logger.info(f"Intelligent persona order for session {session_id}: {top_personas}")
        
        # Generate responses from ONLY the top 3 personas
        responses = []
        
        for persona_id in top_personas:
            try:
                # Generate response from this persona
                persona_result = await chat_orchestrator.chat_with_persona(
                    user_input=message.user_input,
                    persona_id=persona_id,
                    session_id=session_id,
                    response_length=message.response_length or "medium"
                )
                
                if "persona_name" in persona_result and "response" in persona_result:
                    responses.append({
                        "persona": persona_result["persona_name"],
                        "persona_id": persona_result["persona_id"],
                        "response": persona_result["response"]
                    })
                else:
                    # Fallback response
                    responses.append({
                        "persona": chat_orchestrator.personas[persona_id].name,
                        "persona_id": persona_id,
                        "response": "I'm having trouble processing your question right now. Please try again."
                    })
                    
            except Exception as e:
                logger.error(f"Error generating response for persona {persona_id}: {str(e)}")
                # Error fallback
                responses.append({
                    "persona": chat_orchestrator.personas[persona_id].name,
                    "persona_id": persona_id,
                    "response": "I encountered an error while processing your question. Please try again."
                })
        
        return {
            "type": "sequential_responses",
            "responses": responses
        }

    except Exception as e:
        logger.error(f"Error in enhanced sequential chat: {str(e)}")
        return {
            "type": "error", 
            "responses": [{
                "persona": "System",
                "response": "I'm having trouble processing your request. Could you please try again?"
            }]
        }
    
@router.post("/chat/{persona_id}")
async def chat_with_specific_advisor(persona_id: str, input: UserInput, request: Request):
    """Chat with a specific advisor - SAME INTERFACE"""
    try:
        if persona_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request)
        
        # Use new orchestrator
        result = await chat_orchestrator.chat_with_persona(
            user_input=input.user_input,
            persona_id=persona_id,
            session_id=session_id
        )
        
        # FIX: Handle the actual response structure from orchestrator
        if result.get("type") == "single_persona_response" and "persona" in result:
            # New expected structure
            persona_data = result["persona"]
            return {
                "persona": persona_data["persona_name"],
                "persona_id": persona_data["persona_id"],
                "response": persona_data["response"]
            }
        elif "persona_id" in result and "response" in result:
            # Current actual structure from orchestrator
            return {
                "persona": result["persona_name"],
                "persona_id": result["persona_id"],
                "response": result["response"]
            }
        elif result.get("type") == "error" or "error" in result:
            # Error handling
            return {
                "persona": "System",
                "response": result.get("error", "I'm having trouble generating a response right now. Please try again.")
            }
        else:
            # Fallback
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
    """Reply to a specific advisor with proper context"""
    try:
        if reply.advisor_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Advisor '{reply.advisor_id}' not found")

        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request)
        
        # Get the session to access conversation history
        session = session_manager.get_session(session_id)
        
        # Find the original message being replied to for context
        original_message = None
        if reply.original_message_id:
            # Look through session history to find the original message
            for msg in session.messages:
                if getattr(msg, 'id', None) == reply.original_message_id:
                    original_message = msg.content
                    break
        
        # Create context-aware input that includes the reply context
        contextual_input = reply.user_input
        if original_message:
            contextual_input = f"[Replying to your previous message: '{original_message[:100]}...'] {reply.user_input}"
        
        # Use orchestrator with context
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
    
@router.post("/chat/{persona_id}")
async def chat_with_specific_persona(persona_id: str, message: ChatMessage, request: Request):
    """
    Chat with a specific persona - Enhanced with RAG debugging
    
    This endpoint helps debug RAG integration by testing individual personas
    """
    try:
        session_id = get_or_create_session_for_request(request, message.session_id)
        
        # Validate persona exists
        if persona_id not in chat_orchestrator.personas:
            available_personas = list(chat_orchestrator.personas.keys())
            raise HTTPException(
                status_code=400, 
                detail=f"Persona '{persona_id}' not found. Available: {available_personas}"
            )
        
        # Use the enhanced orchestrator method
        result = await chat_orchestrator.chat_with_persona(
            user_input=message.user_input,
            persona_id=persona_id,
            session_id=session_id,
            response_length=message.response_length or "medium"
        )
        
        # Fix: Handle the response structure properly
        if result.get("type") == "single_persona_response" and "persona" in result:
            persona_data = result["persona"]
            
            # Add debugging information
            result["debug_info"] = {
                "persona_id": persona_id,
                "session_id": session_id,
                "query_length": len(message.user_input),
                "rag_manager_available": True,
                "used_documents": persona_data.get("used_documents", False),
                "chunks_used": persona_data.get("document_chunks_used", 0)
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in individual persona chat: {str(e)}")
        return {
            "type": "error",
            "message": f"Error chatting with {persona_id}: {str(e)}",
            "persona_id": persona_id
        }
    
@router.post("/ask/")
async def ask_question(query: PersonaQuery, request: Request):
    """Ask question - SAME INTERFACE"""
    try:
        session_id = get_or_create_session_for_request(request)
        
        # Use the new orchestrator
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