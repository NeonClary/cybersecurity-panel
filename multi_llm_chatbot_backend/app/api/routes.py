import os
from fastapi import APIRouter, Body, HTTPException
import httpx
from app.llm.llm_client import LLMClient
from app.llm.gemini_client import GeminiClient
from app.llm.short_ollama_client import ShortResponseOllamaClient
from app.models.persona import Persona
from app.core.orchestrator import ChatOrchestrator
from app.core.seamless_orchestrator import SeamlessOrchestrator
from app.core.context import GlobalSessionContext
from app.models.default_personas import get_default_personas
from pydantic import BaseModel
from typing import Optional, List
from fastapi import UploadFile, File
from app.utils.document_extractor import extract_text_from_file
from app.core.orchestrator import answer_with_persona_context
from app.utils.chroma_client import add_persona_doc
import hashlib
from app.utils.file_limits import is_within_upload_limit

router = APIRouter()

# Provider management
current_provider = "gemini"
available_providers = ["ollama", "gemini"]

def create_llm_client(provider: str = None) -> LLMClient:
    """Create LLM client based on provider"""
    if provider is None:
        provider = current_provider
        
    if provider == "gemini":
        try:
            return GeminiClient(model_name=os.getenv("GEMINI_MODEL"))
        except ValueError as e:
            # Fallback to Ollama if Gemini API key is not available
            print(f"Gemini API key not found, falling back to Ollama: {e}")
            return ShortResponseOllamaClient(model_name="llama3.2:1b")
    elif provider == "ollama":
        return ShortResponseOllamaClient(model_name="llama3.2:1b")
    else:
        raise ValueError(f"Unknown provider: {provider}")

# Initialize with default provider
llm = create_llm_client()
chat_orchestrator = ChatOrchestrator()
seamless_orchestrator = SeamlessOrchestrator(llm=llm)

session_context = GlobalSessionContext()

# Initialize personas
DEFAULT_PERSONAS = get_default_personas(llm)

for persona in DEFAULT_PERSONAS:
    chat_orchestrator.register_persona(persona)

# Data models
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

# Helper functions for response validation
def _is_valid_response(response: str, persona_id: str) -> bool:
    """Validate response quality"""
    if len(response) < 2 or len(response) > 5000:
        return False
    
    # Check for AI confusion indicators
    confusion_indicators = [
        f"Thank you, Dr. {persona_id.title()}",
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

# Provider management endpoints
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
        # Update current provider
        current_provider = provider_data.provider
        
        # Create new LLM client
        new_llm = create_llm_client(current_provider)
        llm = new_llm
        
        # Update all personas with new LLM
        new_personas = get_default_personas(new_llm)
        chat_orchestrator.personas.clear()
        for persona in new_personas:
            chat_orchestrator.register_persona(persona)
        
        # Update seamless orchestrator
        seamless_orchestrator.llm = new_llm
        
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

# Sequential advisor responses endpoint
@router.post("/chat-sequential")
async def chat_sequential(message: ChatMessage):
    """Generate advisor responses with improved quality controls"""
    
    try:
        orchestrator_result = await seamless_orchestrator.process_message(message.user_input)

        if orchestrator_result["status"] == "orchestrator_asking":
            return {
                "type": "orchestrator_question",
                "responses": [{
                    "persona": "PhD Advisor Assistant",
                    "response": orchestrator_result["orchestrator_question"]
                }],
                "collected_info": orchestrator_result["collected_info"]
            }

        elif orchestrator_result["status"] == "ready_for_advisors":
            enhanced_context = orchestrator_result["enhanced_context"]
            
            # Clear previous advisor responses to avoid confusion
            session_context.clear()
            session_context.append("user", message.user_input)
            session_context.append("orchestrator", enhanced_context)

            advisor_order = chat_orchestrator.get_response_order()
            print("Advisor Order:")
            print(advisor_order)
            responses = []
            
            for persona_id in advisor_order:
                try:
                    persona = chat_orchestrator.personas[persona_id]                    
                    reply = await persona.respond(session_context.full_log, response_length="medium")
                    print("Replies:")
                    print(reply)
                    
                    # Validate response before adding
                    if _is_valid_response(reply, persona_id):
                        responses.append({
                            "persona": persona.name,
                            "persona_id": persona_id,
                            "response": reply,
                        })
                    else:
                        # Fallback response for invalid responses
                        responses.append({
                            "persona": persona.name,
                            "persona_id": persona_id,
                            "response": _get_persona_fallback(persona_id),
                        })

                    session_context.append(persona_id, reply)
                    
                except Exception as e:
                    print(f"Error generating response for {persona_id}: {e}")
                    responses.append({
                        "persona": chat_orchestrator.personas[persona_id].name,
                        "persona_id": persona_id,
                        "response": _get_persona_fallback(persona_id),
                    })

            print("Response Block: " )
            print(responses)
            return {
                "type": "sequential_responses",
                "responses": responses,
                "collected_info": orchestrator_result["collected_info"]
            }
            
    except Exception as e:
        print(f"Error in chat_sequential: {e}")
        return {
            "type": "error",
            "responses": [{
                "persona": "System",
                "response": "I'm having trouble processing your request. Could you please try again?"
            }]
        }


# Individual advisor endpoint with context
@router.post("/chat/{persona_id}")
async def chat_with_specific_advisor(persona_id: str, input: UserInput):
    """Chat with a specific advisor"""
    try:
        if persona_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

        session_context.append("user", input.user_input)
        persona = chat_orchestrator.personas[persona_id]
        context = session_context.full_log.copy()
        reply = await persona.respond(context, response_length="medium")
        session_context.append(persona_id, reply)

        return {
            "persona": persona.name,
            "persona_id": persona_id,
            "response": reply
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat_with_specific_advisor: {e}")
        return {
            "persona": "System",
            "response": "I'm having trouble generating a response right now. Please try again."
        }

# Reply to specific advisor endpoint
@router.post("/reply-to-advisor")
async def reply_to_advisor(reply: ReplyToAdvisor):
    """Reply to a specific advisor and get response only from that advisor"""
    
    try:
        if reply.advisor_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Advisor '{reply.advisor_id}' not found")

        # Add user reply to context
        session_context.append("user", reply.user_input)

        # Get response from specific advisor
        persona = chat_orchestrator.personas[reply.advisor_id]
        
        # Generate response
        reply_response = await persona.respond(session_context.full_log, response_length="medium")
        session_context.append(reply.advisor_id, reply_response)
        
        return {
            "type": "advisor_reply",
            "persona": persona.name,
            "persona_id": reply.advisor_id,
            "response": reply_response,
            "original_message_id": reply.original_message_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in reply_to_advisor: {e}")
        return {
            "type": "error",
            "persona": "System",
            "response": "I'm having trouble generating a reply right now. Please try again."
        }

# Reset session
@router.post("/reset-session")
async def reset_session():
    try:
        seamless_orchestrator.reset()
        session_context.clear()
        return {"status": "reset", "message": "Session reset successfully"}
    except Exception as e:
        print(f"Error resetting session: {e}")
        return {"status": "error", "message": "Failed to reset session"}

# Context inspection
@router.get("/context")
def get_context():
    return session_context.full_log

# Legacy model switching endpoint (now redirects to provider switching)
@router.post("/switch-model")
async def switch_model(model_name: str = Body(...)):
    # For backward compatibility, try to map model names to providers
    if "gemini" in model_name.lower():
        return await switch_provider(ProviderSwitch(provider="gemini"))
    else:
        return await switch_provider(ProviderSwitch(provider="ollama"))

@router.get("/current-model")
async def get_current_model():
    # For backward compatibility
    model_name = llm.model_name if hasattr(llm, 'model_name') else "gemini-2.0-flash"
    return {
        "model": model_name,
        "provider": current_provider
    }

@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    # Validate file type
    if file.content_type not in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    try:
        # Read file bytes
        file_bytes = await file.read()

        # Check file size limit
        if not is_within_upload_limit("default", file_bytes, session_context):
            raise HTTPException(status_code=400, detail="Upload exceeds session document size limit (10 MB).")

        # Extract and validate text
        content = extract_text_from_file(file_bytes, file.content_type)
        if not content.strip():
            raise HTTPException(status_code=400, detail="Document is empty or unreadable.")

        # Track file size and name
        session_context.append("Document", f"[Uploaded Document Content]\n{content.strip()}")
        session_context.uploaded_files.append(file.filename)
        session_context.total_upload_size += len(file_bytes)

        return {"message": "Document uploaded and added to context successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

# Debug endpoint
@router.get("/debug/personas")
async def debug_personas():
    return {
        "personas": {
            pid: {
                "name": persona.name,
                "prompt": persona.system_prompt[:100] + "..."
            } for pid, persona in chat_orchestrator.personas.items()
        },
        "context_length": len(session_context.full_log),
        "current_provider": current_provider
    }

class PersonaQuery(BaseModel):
    question: str
    persona: str

@router.post("/ask/")
async def ask_question(query: PersonaQuery):
    response = await answer_with_persona_context(query.question, query.persona)
    
    # Store Q&A in vector DB
    combined_text = f"Q: {query.question}\nA: {response}"
    doc_id = hashlib.md5(combined_text.encode()).hexdigest()  # Create a unique doc ID
    
    add_persona_doc(combined_text, query.persona, doc_id)

    return {"response": response}

@router.get("/uploaded-files")
def get_uploaded_filenames():
    return {"files": session_context.uploaded_files}
