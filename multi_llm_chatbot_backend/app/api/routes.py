from fastapi import APIRouter, Body, HTTPException
from app.llm.mistral_client import MistralClient
from app.models.persona import Persona
from app.core.orchestrator import ChatOrchestrator
from app.core.seamless_orchestrator import SeamlessOrchestrator
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

# Initialize LLM and orchestrators
llm = MistralClient()
chat_orchestrator = ChatOrchestrator()
seamless_orchestrator = SeamlessOrchestrator()

# Global context storage
class GlobalSessionContext:
    def __init__(self):
        self.full_log: list[dict] = []

    def append(self, role: str, content: str):
        self.full_log.append({"role": role, "content": content})

    def filter_by_persona(self, persona_id: str):
        return [msg for msg in self.full_log if msg["role"] in ("user", persona_id)]

    def clear(self):
        self.full_log = []

session_context = GlobalSessionContext()

# Default personas
DEFAULT_PERSONAS = [
    Persona(
        id="methodist",
        name="Methodist Advisor",
        system_prompt="You are a highly methodical PhD advisor who believes in structure and planning. Provide organized, step-by-step guidance.",
        llm=llm
    ),
    Persona(
        id="theorist",
        name="Theorist Advisor",
        system_prompt="You are a philosophical PhD advisor who focuses on abstract theories and ideas. Help students think deeply about concepts and frameworks.",
        llm=llm
    ),
    Persona(
        id="pragmatist",
        name="Pragmatist Advisor",
        system_prompt="You are a practical PhD advisor who focuses on real-world outcomes and utility. Give actionable, concrete advice.",
        llm=llm
    )
]

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

# Main chat endpoint with seamless orchestrator
@router.post("/chat")
async def chat_with_orchestrator(message: ChatMessage):
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

        chat_orchestrator.set_active_personas(["methodist", "theorist", "pragmatist"])
        session_context.append("user", enhanced_context)

        advisor_responses = []
        for persona_id in chat_orchestrator.get_active_personas():
            persona = chat_orchestrator.personas[persona_id]
            context = session_context.full_log
            reply = await persona.respond(context)
            session_context.append(persona_id, reply)
            advisor_responses.append({"persona": persona.name, "response": reply})

        return {
            "type": "advisor_responses",
            "responses": advisor_responses,
            "collected_info": orchestrator_result["collected_info"]
        }

    return {
        "type": "error",
        "responses": [{
            "persona": "System",
            "response": "I'm having trouble processing your request. Could you please try again?"
        }]
    }

# Reset both orchestrators
@router.post("/reset-session")
async def reset_session():
    seamless_orchestrator.reset()
    chat_orchestrator.history = []
    session_context.clear()
    return {"status": "reset", "message": "Session reset successfully"}

# Direct chat bypassing seamless orchestrator
@router.post("/chat-direct")
async def chat_direct(
    user_input: str = Body(...),
    active_personas: List[str] = Body(default=["methodist", "theorist", "pragmatist"])
):
    chat_orchestrator.set_active_personas(active_personas)
    session_context.append("user", user_input)

    responses = []
    for persona_id in active_personas:
        persona = chat_orchestrator.personas[persona_id]
        context = session_context.full_log
        reply = await persona.respond(context)
        session_context.append(persona_id, reply)
        responses.append({"persona": persona.name, "response": reply})

    return responses

# Individual persona endpoint
@router.post("/chat/{persona_id}")
async def chat_with_persona(persona_id: str, input: UserInput, skip_user_append: bool = False):
    if persona_id not in chat_orchestrator.personas:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

    if not skip_user_append:
        session_context.append("user", input.user_input)

    persona = chat_orchestrator.personas[persona_id]
    context = session_context.filter_by_persona(persona_id)
    reply = await persona.respond(context)
    session_context.append(persona_id, reply)

    return {"persona": persona.name, "response": reply}

# Persona management
@router.post("/personas/add")
async def add_persona(input: PersonaInput):
    if input.id in chat_orchestrator.personas:
        raise HTTPException(status_code=400, detail=f"Persona '{input.id}' already exists")

    new_persona = Persona(
        id=input.id,
        name=input.name,
        system_prompt=input.system_prompt,
        llm=llm
    )
    chat_orchestrator.register_persona(new_persona)
    return {"message": f"Persona '{input.name}' added successfully."}

@router.post("/personas/remove")
async def remove_persona(persona_id: str = Body(...)):
    if persona_id not in chat_orchestrator.personas:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

    del chat_orchestrator.personas[persona_id]
    return {"message": f"Persona '{persona_id}' removed successfully."}

@router.get("/personas")
async def list_personas():
    return list(chat_orchestrator.personas.keys())

# Context inspection
@router.get("/context")
def get_context():
    return session_context.full_log

@router.post("/reset")
async def reset_context():
    session_context.clear()
    return {"message": "Context reset successfully"}
