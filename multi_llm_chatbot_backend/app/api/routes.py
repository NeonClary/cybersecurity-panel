import os
from fastapi import APIRouter, Body, HTTPException
import httpx
from app.llm.llm_client import LLMClient
from app.llm.gemini_client import GeminiClient
from app.models.persona import Persona
from app.core.orchestrator import ChatOrchestrator
from app.core.seamless_orchestrator import SeamlessOrchestrator
from app.core.context import GlobalSessionContext
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

# Improved LLM client with better short response handling for Ollama
class ShortResponseOllamaClient(LLMClient):
    def __init__(self, model_name: str = "llama3.2:1b"):
        self.model_name = model_name
    
    async def generate(self, system_prompt: str, context: List[dict]) -> str:
        # Build cleaner context - only include recent relevant messages
        recent_context = context[-3:] if len(context) > 3 else context
        
        # Create a focused prompt
        prompt_parts = [system_prompt]
        
        # Add only the user's current question
        for msg in recent_context:
            if msg['role'] == 'user':
                prompt_parts.append(f"Student Question: {msg['content']}")
                break  # Only use the most recent user message
        
        prompt_parts.append("Your Response:")
        prompt = "\n\n".join(prompt_parts)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": 80,  # Reduced from 200 to force shorter responses
                "repeat_penalty": 1.1,
                "stop": ["\n\n", "Student:", "Question:", "Response:"]  # Stop tokens
            }
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post("http://localhost:11434/api/generate", json=payload)
                response.raise_for_status()
                result = response.json().get("response", "[No response]").strip()
                
                # Enhanced cleanup
                result = self._clean_response(result)
                
                # Validate response quality
                if len(result) < 20 or self._is_poor_quality(result):
                    return self._get_fallback_response()
                
                return result
                
        except Exception as e:
            return "I'm having trouble generating a response right now. Please try again."
    
    def _clean_response(self, response: str) -> str:
        """Clean up common response issues"""
        # Remove common prefixes
        prefixes_to_remove = [
            "Here are 2-3 sentence", "Here's an expansion", "Assistant:",
            "Dr. Methodist:", "Dr. Theorist:", "Dr. Pragmatist:",
            "Methodist Advisor:", "Theorist Advisor:", "Pragmatist Advisor:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Remove trailing incomplete sentences
        sentences = response.split('.')
        if len(sentences) > 1 and len(sentences[-1].strip()) < 10:
            response = '.'.join(sentences[:-1]) + '.'
        
        # Remove excessive academic fluff
        fluff_patterns = [
            "conceptual insights:", "actionable advice:", "my inquisitive student",
            "excellent question", "thank you for", "assistant!"
        ]
        
        for pattern in fluff_patterns:
            response = response.replace(pattern, "").strip()
        
        return response
    
    def _is_poor_quality(self, response: str) -> bool:
        """Check if response quality is poor"""
        poor_indicators = [
            "Thank you, Dr." in response,  # AI confusion about identity
            "Assistant:" in response,
            len(response.split()) > 100,  # Too verbose
            response.count("?") > 3,  # Too many questions
        ]
        return any(poor_indicators)
    
    def _get_fallback_response(self) -> str:
        """Return a simple fallback when quality is poor"""
        return "I'd be happy to help with that. Could you provide more specific details about what you're looking for?"

# Initialize with default provider
llm = create_llm_client()
chat_orchestrator = ChatOrchestrator()
seamless_orchestrator = SeamlessOrchestrator(llm=llm)

session_context = GlobalSessionContext()

def create_default_personas(llm_client: LLMClient):
    """Create default personas with improved, concise system prompts"""
    return [
        Persona(
            id="methodist",
            name="Dr. Methodist",
            system_prompt="""You are Dr. Methodist, a research methodology expert.

RESPONSE RULES:
- Maximum 3 sentences
- Start with your recommendation 
- Include ONE specific actionable step
- Use terms like "validity," "operationalize," "sampling frame"
- Focus on methodological rigor

TONE: Precise, helpful, focused on research design quality.

Example: "Use a cautious tone unless your methodology is exceptionally robust. Strong validity and clear operationalization justify more confident language. Next step: Review your methods section to assess how assertive you can be.""",
            llm=llm_client
        ),
        Persona(
            id="theorist",
            name="Dr. Theorist", 
            system_prompt="""You are Dr. Theorist, a conceptual frameworks expert.
            RESPONSE RULES:
            - Maximum 3 sentences
            - Start with conceptual perspective
            - Reference theoretical positioning
            - Ask ONE probing question when relevant
            - Use terms like "epistemological," "framework," "assumptions"

            TONE: Thoughtful, intellectually rigorous, conceptually focused.

            Example: "Your tone should reflect your epistemological stance—bold if challenging frameworks, cautious if extending theory. Consider your relationship to existing literature. What theoretical assumptions underlie your approach?""",
            llm=llm_client
        ),
        Persona(
            id="pragmatist",
            name="Dr. Pragmatist",
            system_prompt="""You are Dr. Pragmatist, a practical action-focused advisor.

RESPONSE RULES:
- Maximum 2 sentences
- Start with clear, actionable advice
- Focus on immediate next steps
- Use phrases like "Quick fix:" "Next step:" "Try this:"
- Prioritize progress over perfection

TONE: Warm, motivational, results-oriented.

Example: "Start cautious and earn the right to be bold as you build your case. Quick fix: Use 'This study suggests...' rather than 'This study proves...'""",
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

# Helper functions for response validation
def _is_valid_response(response: str, persona_id: str) -> bool:
    """Validate response quality"""
    if len(response) < 20 or len(response) > 500:
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
            session_context.append("user", enhanced_context)

            advisor_order = ["methodist", "theorist", "pragmatist"]
            responses = []
            
            for i, persona_id in enumerate(advisor_order):
                try:
                    persona = chat_orchestrator.personas[persona_id]
                    
                    # Use clean context for each advisor (no cross-contamination)
                    clean_context = [{"role": "user", "content": enhanced_context}]
                    
                    reply = await persona.respond(clean_context)
                    
                    # Validate response before adding
                    if _is_valid_response(reply, persona_id):
                        responses.append({
                            "persona": persona.name,
                            "persona_id": persona_id,
                            "response": reply,
                            "order": i
                        })
                    else:
                        # Fallback response for invalid responses
                        responses.append({
                            "persona": persona.name,
                            "persona_id": persona_id,
                            "response": _get_persona_fallback(persona_id),
                            "order": i
                        })
                    
                except Exception as e:
                    print(f"Error generating response for {persona_id}: {e}")
                    responses.append({
                        "persona": chat_orchestrator.personas[persona_id].name,
                        "persona_id": persona_id,
                        "response": _get_persona_fallback(persona_id),
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
        session_context.append("user", f"[Uploaded Document Content]\n{content.strip()}")
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
