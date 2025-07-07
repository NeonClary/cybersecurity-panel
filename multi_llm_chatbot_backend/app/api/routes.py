import os
from fastapi import APIRouter, Body, HTTPException, Header, UploadFile, File, Request
from typing import Optional, List
import httpx
from app.llm.llm_client import LLMClient
from app.llm.improved_gemini_client import ImprovedGeminiClient
from app.llm.improved_ollama_client import ImprovedOllamaClient
from app.models.persona import Persona
from app.core.improved_orchestrator import ImprovedChatOrchestrator
from app.core.session_manager import get_session_manager
from app.models.default_personas import get_default_personas
from app.utils.document_extractor import extract_text_from_file
from app.utils.file_limits import is_within_upload_limit
from pydantic import BaseModel
import hashlib
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Provider management (same as before)
current_provider = "gemini"
available_providers = ["ollama", "gemini"]

def create_llm_client(provider: str = None) -> LLMClient:
    """Create LLM client based on provider"""
    if provider is None:
        provider = current_provider
        
    if provider == "gemini":
        try:
            return ImprovedGeminiClient(model_name=os.getenv("GEMINI_MODEL"))
        except ValueError as e:
            logger.warning(f"Gemini API key not found, falling back to Ollama: {e}")
            return ImprovedOllamaClient(model_name="llama3.2:1b")
    elif provider == "ollama":
        return ImprovedOllamaClient(model_name="llama3.2:1b")
    else:
        raise ValueError(f"Unknown provider: {provider}")

# Initialize with default provider
llm = create_llm_client()
chat_orchestrator = ImprovedChatOrchestrator()
session_manager = get_session_manager()

# Initialize personas
DEFAULT_PERSONAS = get_default_personas(llm)
for persona in DEFAULT_PERSONAS:
    chat_orchestrator.register_persona(persona)

# Keep all the same data models as before
class UserInput(BaseModel):
    user_input: str

class PersonaInput(BaseModel):
    id: str
    name: str
    system_prompt: str

class ChatMessage(BaseModel):
    user_input: str
    session_id: Optional[str] = None
    response_length: Optional[str] = "medium"

class ReplyToAdvisor(BaseModel):
    user_input: str
    advisor_id: str
    original_message_id: Optional[str] = None

class ProviderSwitch(BaseModel):
    provider: str

# ==============================================================
# SESSION MANAGEMENT COMPATIBILITY LAYER
# ==============================================================

def get_or_create_session_for_request(request: Request, 
                                    session_id_override: Optional[str] = None) -> str:
    """
    Get or create session for request using multiple strategies:
    1. Use provided session_id if given
    2. Use X-Session-ID header if present  
    3. Use client IP as fallback for backward compatibility
    4. Create new session if nothing available
    
    This allows the old stateless API to work with session management
    """
    # Strategy 1: Explicit session ID (for new clients)
    if session_id_override:
        return session_id_override
    
    # Strategy 2: Check for session header (optional for frontend)
    session_header = request.headers.get("X-Session-ID")
    if session_header:
        return session_header
    
    # Strategy 3: Use client IP for backward compatibility
    # This gives each client IP their own persistent session
    client_ip = request.client.host if request.client else "unknown"
    ip_session_id = f"ip_{client_ip}"
    
    # Get or create session for this IP
    session = session_manager.get_session(ip_session_id)
    return session.session_id



# Helper functions (same as before)
def _is_valid_response(response: str, persona_id: str) -> bool:
    """Validate response quality"""
    if len(response) < 2 or len(response) > 5000:
        return False
    
    confusion_indicators = [
        f"Thank you, Dr. {persona_id.title()}",
        "Assistant:",
        f"Dr. {persona_id.title()}",
        "Assistant:",
        f"Dr. {persona_id.title()} Advisor:",
        "excellent discussion, Assistant"
    ]
    
    return not any(indicator in response for indicator in confusion_indicators)

def _get_persona_fallback(persona_id: str) -> str:
    """Get persona-specific fallback responses"""
    fallbacks = {
        "methodist": "Focus on ensuring your methodology aligns with your research question. What specific method are you considering?",
        "theorist": "Consider the theoretical framework underlying your approach. What assumptions guide your thinking?",
        "pragmatist": "Let's break this down into actionable steps. What's the most important thing you need to decide today?"
    }
    return fallbacks.get(persona_id, "I'd be happy to help. Could you provide more details?")

# Provider management endpoints (EXACTLY THE SAME)
@router.get("/current-provider")
async def get_current_provider():
    return {
        "current_provider": current_provider,
        "available_providers": available_providers,
        "model_info": {
            "name": llm.model_name if hasattr(llm, 'model_name') else "gemini-2.0-flash",
            "provider": current_provider
        }
    }

@router.post("/switch-provider")
async def switch_provider(provider_data: ProviderSwitch):
    global current_provider, llm
    
    if provider_data.provider not in available_providers:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown provider: {provider_data.provider}. Available: {available_providers}"
        )
    
    try:
        current_provider = provider_data.provider
        new_llm = create_llm_client(current_provider)
        llm = new_llm
        
        new_personas = get_default_personas(new_llm)
        chat_orchestrator.personas.clear()
        for persona in new_personas:
            chat_orchestrator.register_persona(persona)
        
        return {
            "message": f"Successfully switched to {current_provider}",
            "current_provider": current_provider,
            "model_info": {
                "name": new_llm.model_name if hasattr(new_llm, 'model_name') else "gemini-2.0-flash",
                "provider": current_provider
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch to {provider_data.provider}: {str(e)}"
        )

# Main chat endpoint (SAME INTERFACE, improved backend)
@router.post("/chat-sequential")
async def chat_sequential(message: ChatMessage, request: Request):
    """
    SAME INTERFACE AS BEFORE - Generate advisor responses 
    Now with improved session management behind the scenes
    """
    try:
        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request, message.session_id)
        
        # Use the new orchestrator with session management
        result = await chat_orchestrator.process_message(
            user_input=message.user_input,
            session_id=session_id,
            response_length=message.response_length
        )
        
        # Convert new format back to old format for backward compatibility
        if result["type"] == "clarification":
            return {
                "type": "orchestrator_question",
                "responses": [{
                    "persona": "PhD Advisor Assistant",
                    "response": result["message"]
                }],
                "collected_info": {}
            }
        
        elif result["type"] == "persona_responses":
            # Convert new response format to old format
            return {
                "type": "sequential_responses", 
                "responses": [
                    {
                        "persona": resp["persona_name"],
                        "persona_id": resp["persona_id"],
                        "response": resp["response"]
                    }
                    for resp in result["responses"]
                ],
                "collected_info": {}
            }
        
        else:
            return {
                "type": "error",
                "responses": [{
                    "persona": "System",
                    "response": result.get("message", "Please try again.")
                }]
            }
            
    except Exception as e:
        logger.error(f"Error in chat_sequential: {e}")
        return {
            "type": "error",
            "responses": [{
                "persona": "System",
                "response": "I'm having trouble processing your request. Could you please try again?"
            }]
        }

# Individual advisor endpoint (SAME INTERFACE)
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
        
        if result["type"] == "single_persona_response":
            persona_data = result["persona"]
            return {
                "persona": persona_data["persona_name"],
                "persona_id": persona_data["persona_id"],
                "response": persona_data["response"]
            }
        else:
            return {
                "persona": "System",
                "response": result.get("message", "I'm having trouble generating a response right now. Please try again.")
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat_with_specific_advisor: {e}")
        return {
            "persona": "System",
            "response": "I'm having trouble generating a response right now. Please try again."
        }

# Reply to advisor endpoint (SAME INTERFACE)
@router.post("/reply-to-advisor")
async def reply_to_advisor(reply: ReplyToAdvisor, request: Request):
    """Reply to a specific advisor - SAME INTERFACE"""
    try:
        if reply.advisor_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Advisor '{reply.advisor_id}' not found")

        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request)
        
        # Use new orchestrator
        result = await chat_orchestrator.chat_with_persona(
            user_input=reply.user_input,
            persona_id=reply.advisor_id,
            session_id=session_id
        )
        
        if result["type"] == "single_persona_response":
            persona_data = result["persona"]
            return {
                "type": "advisor_reply",
                "persona": persona_data["persona_name"],
                "persona_id": persona_data["persona_id"],
                "response": persona_data["response"],
                "original_message_id": reply.original_message_id
            }
        else:
            return {
                "type": "error",
                "persona": "System",
                "response": result.get("message", "I'm having trouble generating a reply right now. Please try again.")
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

# Document upload (SAME INTERFACE)
@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...), request: Request = None):
    """Upload document - SAME INTERFACE"""
    if file.content_type not in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    try:
        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        
        file_bytes = await file.read()

        # Simple size check
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Upload exceeds session document size limit (10 MB).")

        content = extract_text_from_file(file_bytes, file.content_type)
        if not content.strip():
            raise HTTPException(status_code=400, detail="Document is empty or unreadable.")

        # Add to session context using new system
        session.add_uploaded_file(file.filename, content, len(file_bytes))

        return {"message": "Document uploaded and added to context successfully."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

# Get uploaded files (SAME INTERFACE)
@router.get("/uploaded-files")
async def get_uploaded_filenames(request: Request):
    """Get uploaded files - SAME INTERFACE"""
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        return {"files": session.uploaded_files}
    except Exception as e:
        logger.error(f"Error getting uploaded files: {str(e)}")
        return {"files": []}

# Context endpoint (SAME INTERFACE)
@router.get("/context")
async def get_context(request: Request):
    """Get context - SAME INTERFACE"""
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        return session.messages  # Return messages in same format as before
    except Exception as e:
        logger.error(f"Error getting context: {str(e)}")
        return []

# Reset session (SAME INTERFACE) 
@router.post("/reset-session")
async def reset_session(request: Request):
    """Reset session - SAME INTERFACE"""
    try:
        session_id = get_or_create_session_for_request(request)
        success = chat_orchestrator.reset_session(session_id)
        
        if success:
            return {"status": "reset", "message": "Session reset successfully"}
        else:
            return {"status": "error", "message": "Failed to reset session"}
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        return {"status": "error", "message": "Failed to reset session"}

# Legacy model endpoints (SAME INTERFACE)
@router.post("/switch-model")
async def switch_model(model_name: str = Body(...)):
    """Legacy model switching - SAME INTERFACE"""
    if "gemini" in model_name.lower():
        return await switch_provider(ProviderSwitch(provider="gemini"))
    else:
        return await switch_provider(ProviderSwitch(provider="ollama"))

@router.get("/current-model")
async def get_current_model():
    """Legacy model info - SAME INTERFACE"""
    model_name = llm.model_name if hasattr(llm, 'model_name') else "gemini-2.0-flash"
    return {
        "model": model_name,
        "provider": current_provider
    }

# Debug endpoint (SAME INTERFACE)
@router.get("/debug/personas")
async def debug_personas(request: Request):
    """Debug personas - SAME INTERFACE"""
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        
        return {
            "personas": {
                pid: {
                    "name": persona.name,
                    "prompt": persona.system_prompt[:100] + "..."
                } for pid, persona in chat_orchestrator.personas.items()
            },
            "context_length": len(session.messages),
            "current_provider": current_provider
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        return {
            "personas": {},
            "context_length": 0,
            "current_provider": current_provider
        }

# Ask endpoint (SAME INTERFACE)
class PersonaQuery(BaseModel):
    question: str
    persona: str

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

# Root endpoint (SAME INTERFACE)
@router.get("/")
def root():
    """Root endpoint - SAME INTERFACE with updated info"""
    return {
        "message": "Multi-LLM PhD Advisor Backend is up and running",
        "version": "1.0.0",  # Updated version 
        "features": [
            "Improved Session Management",
            "Unified Context Handling", 
            "Ollama Support", 
            "Gemini API Support", 
            "Provider Switching"
        ]
    }