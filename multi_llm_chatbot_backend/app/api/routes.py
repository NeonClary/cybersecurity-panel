from fastapi import APIRouter, Body
from app.llm.mistral_client import MistralClient
from app.models.persona import Persona
from app.core.orchestrator import ChatOrchestrator
from app.core.seamless_orchestrator import SeamlessOrchestrator
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

# Singletons
llm = MistralClient()
chat_orchestrator = ChatOrchestrator()
seamless_orchestrator = SeamlessOrchestrator()

# Register personas
chat_orchestrator.register_persona(Persona(
    id="methodist",
    name="Methodist Advisor",
    system_prompt="You are a highly methodical PhD advisor who believes in structure and planning. Provide organized, step-by-step guidance.",
    llm=llm
))

chat_orchestrator.register_persona(Persona(
    id="theorist", 
    name="Theorist Advisor",
    system_prompt="You are a philosophical PhD advisor who focuses on abstract theories and ideas. Help students think deeply about concepts and frameworks.",
    llm=llm
))

chat_orchestrator.register_persona(Persona(
    id="pragmatist",
    name="Pragmatist Advisor", 
    system_prompt="You are a practical PhD advisor who focuses on real-world outcomes and utility. Give actionable, concrete advice.",
    llm=llm
))

class ChatMessage(BaseModel):
    user_input: str
    session_id: Optional[str] = None

@router.post("/chat")
async def chat_with_orchestrator(message: ChatMessage):
    """Main chat endpoint with seamless orchestrator integration"""
    
    # Process message through seamless orchestrator
    orchestrator_result = await seamless_orchestrator.process_message(message.user_input)
    
    if orchestrator_result["status"] == "orchestrator_asking":
        # Orchestrator needs more info - return orchestrator question
        return {
            "type": "orchestrator_question",
            "responses": [{
                "persona": "PhD Advisor Assistant", 
                "response": orchestrator_result["orchestrator_question"]
            }],
            "collected_info": orchestrator_result["collected_info"]
        }
    
    elif orchestrator_result["status"] == "ready_for_advisors":
        # Ready for advisor consultation
        enhanced_context = orchestrator_result["enhanced_context"]
        
        # Set active advisors
        chat_orchestrator.set_active_personas(["methodist", "theorist", "pragmatist"])
        
        # Get advisor responses
        advisor_responses = await chat_orchestrator.process_user_input(enhanced_context)
        
        return {
            "type": "advisor_responses",
            "responses": advisor_responses,
            "collected_info": orchestrator_result["collected_info"]
        }
    
    # Fallback - shouldn't reach here normally
    return {
        "type": "error",
        "responses": [{
            "persona": "System",
            "response": "I'm having trouble processing your request. Could you please try again?"
        }]
    }

@router.post("/reset-session")
async def reset_session():
    """Reset the orchestrator session"""
    seamless_orchestrator.reset()
    # Also reset chat orchestrator history if needed
    chat_orchestrator.history = []
    return {"status": "reset", "message": "Session reset successfully"}

# Keep the old endpoints for backward compatibility
@router.post("/chat-direct") 
async def chat_direct(
    user_input: str = Body(...),
    active_personas: List[str] = Body(default=["methodist", "theorist", "pragmatist"])
):
    """Direct chat endpoint bypassing orchestrator (for testing)"""
    chat_orchestrator.set_active_personas(active_personas)
    responses = await chat_orchestrator.process_user_input(user_input)
    return responses