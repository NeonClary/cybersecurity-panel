import os
from fastapi import APIRouter, Body, HTTPException
import httpx
from app.llm.llm_client import LLMClient
from app.llm.gemini_client import GeminiClient
from app.models.persona import Persona
from app.core.orchestrator import ChatOrchestrator
from app.core.seamless_orchestrator import SeamlessOrchestrator
from pydantic import BaseModel
from typing import Optional, List
from fastapi import UploadFile, File
from app.utils.document_extractor import extract_text_from_file

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
            return GeminiClient(model_name = os.getenv("GEMINI_MODEL"))
        except ValueError as e:
            # Fallback to Ollama if Gemini API key is not available
            print(f"Gemini API key not found, falling back to Ollama: {e}")
            return ShortResponseOllamaClient(model_name="llama3.2:1b")
    elif provider == "ollama":
        return ShortResponseOllamaClient(model_name="llama3.2:1b")
    else:
        raise ValueError(f"Unknown provider: {provider}")

# Improved LLM client with better short response handling for Ollama
class ShortResponseOllamaClient(LLMClient):
    def __init__(self, model_name: str = "llama3.2:1b"):
        self.model_name = model_name
    
    async def generate(self, system_prompt: str, context: List[dict]) -> str:
        # Create a more natural conversation format
        messages = []
        
        # Add system message
        if system_prompt:
            messages.append(f"System: {system_prompt}")
        
        # Add conversation history
        for msg in context:
            role = msg['role'].capitalize()
            if role == "User":
                messages.append(f"Student: {msg['content']}")
            elif role in ["Methodist", "Theorist", "Pragmatist"]:
                messages.append(f"{role} Advisor: {msg['content']}")
            else:
                messages.append(f"{role}: {msg['content']}")
        
        # Create the final prompt
        conversation = "\n".join(messages)
        prompt = f"{conversation}\n\nAssistant:"
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": 200,
                "repeat_penalty": 1.1,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post("http://localhost:11434/api/generate", json=payload)
                response.raise_for_status()
                result = response.json().get("response", "[No response]").strip()
                
                # Clean up common issues
                result = result.replace("Here are 2-3 sentence", "").strip()
                result = result.replace("Here's an expansion of the advice:", "").strip()
                result = result.replace("conceptual insights:", "").strip()
                result = result.replace("actionable advice:", "").strip()
                
                # If response is too short or just punctuation, return a fallback
                if len(result) < 10 or result in [":", ".", ""]:
                    return "I'd be happy to help with that. Could you provide more specific details about what you're looking for?"
                
                return result
                
        except Exception as e:
            return f"I apologize, but I'm having trouble generating a response right now. Please try again."

# Initialize with default provider
llm = create_llm_client()
chat_orchestrator = ChatOrchestrator()
seamless_orchestrator = SeamlessOrchestrator(llm=llm)

# Global context storage
class GlobalSessionContext:
    def __init__(self):
        self.full_log: list[dict] = []

    def append(self, role: str, content: str):
        self.full_log.append({"role": role, "content": content})

    def filter_by_persona(self, persona_id: str):
        return self.full_log

    def clear(self):
        self.full_log = []

session_context = GlobalSessionContext()

def create_default_personas(llm_client: LLMClient):
    """Create default personas with given LLM client"""
    return [
        Persona(
            id="methodist",
            name="Methodist Advisor",
            system_prompt="You are Dr. Methodist — a meticulous, discipline-neutral advisor who specializes in research design, methodology, and validity." \
            "Your primary concern is whether the student's research plan is methodologically sound, feasible, and aligned with their stated research question." \
            "You value clarity, precision, and logical alignment between claims, methods, and outcomes. You often use language like “operationalize,”" \
            "“sampling frame,” “construct validity,” and “replication.” You frequently ask students to explain why a method is appropriate and whether " \
            "alternative designs might be more rigorous or parsimonious. You are not rude or dismissive, but you don’t sugarcoat weak designs. You believe" \
            " good methods are teachable and worth defending. Always explain your reasoning and, if appropriate, recommend ways to tighten or clarify the student’s approach.",
            llm=llm_client
        ),
        Persona(
            id="theorist",
            name="Theorist Advisor", 
            system_prompt="You are Dr. Theorist — an intellectually deep advisor who focuses on conceptual clarity, theoretical framing, and epistemological depth. You " \
            "are most helpful when a student needs to articulate, refine, or rethink the theoretical foundations of their work. You often ask questions like " \
            "“What assumptions underlie this framework?” or “How does this relate to tradition X or thinker Y?” You encourage students to think about ontology, " \
            "positionality, and the meaning of key terms in their research. You reference theories, concepts, and debates — especially from the humanities and " \
            "social sciences — to help students sharpen their ideas. Your tone is thoughtful and reflective. You don’t rush to judgment but probe until the student's" \
            " conceptual scaffolding is robust. Avoid vague praise or technical critique — your role is to illuminate the deeper structure of ideas.",
            llm=llm_client
        ),
        Persona(
            id="pragmatist",
            name="Pragmatist Advisor",
            system_prompt="You are The Pragmatist — an action-focused advisor who helps students move forward when they feel overwhelmed, stuck, or overthinking. You " \
            "prioritize clarity over perfection, progress over polish, and “done” over ideal. You frequently say things like “Let’s break this down” or “What’s one thing" \
            " you can do today?” You are warm, practical, and motivational. You don’t dwell on critique unless it helps unblock the student. You are especially helpful during" \
            " early drafts, decision paralysis, or writer’s block. Your suggestions should be immediately actionable, even if they’re not perfect. Always focus on the next step,"
            " and help reduce cognitive load wherever possible.",
            llm=llm_client
        )
    ]

# Initialize personas
DEFAULT_PERSONAS = create_default_personas(llm)
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

class ReplyToAdvisor(BaseModel):
    user_input: str
    advisor_id: str
    original_message_id: Optional[str] = None

class ProviderSwitch(BaseModel):
    provider: str

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
        new_personas = create_default_personas(new_llm)
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
    """Generate advisor responses one by one for faster perceived response time"""
    
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
            session_context.append("user", enhanced_context)

            # Generate responses sequentially
            advisor_order = ["methodist", "theorist", "pragmatist"]
            responses = []
            
            for i, persona_id in enumerate(advisor_order):
                try:
                    persona = chat_orchestrator.personas[persona_id]
                    # Get current context up to this point
                    context = session_context.full_log.copy()
                    
                    # Generate response
                    reply = await persona.respond(context)
                    
                    # Add this advisor's response to context for next advisor
                    session_context.append(persona_id, reply)
                    
                    responses.append({
                        "persona": persona.name,
                        "persona_id": persona_id,
                        "response": reply,
                        "order": i
                    })
                    
                except Exception as e:
                    print(f"Error generating response for {persona_id}: {e}")
                    responses.append({
                        "persona": chat_orchestrator.personas[persona_id].name,
                        "persona_id": persona_id,
                        "response": "I'm having trouble generating a response right now. Please try again.",
                        "order": i
                    })

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

# Main chat endpoint (keep for compatibility)
@router.post("/chat")
async def chat_with_orchestrator(message: ChatMessage):
    """Redirect to sequential endpoint for better UX"""
    return await chat_sequential(message)

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
        reply = await persona.respond(context)
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
        context = session_context.full_log.copy()
        
        # Generate response
        reply_response = await persona.respond(context)
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
    if file.content_type not in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    try:
        # Read file content into memory
        contents = await file.read()

        # Now pass raw contents and file type to extractor
        content = extract_text_from_file(contents, file.content_type)

        if not content.strip():
            raise HTTPException(status_code=400, detail="Document is empty or unreadable.")

        session_context.append("user", f"[Uploaded Document Content]\n{content.strip()}")

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