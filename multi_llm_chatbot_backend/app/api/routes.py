from fastapi import APIRouter, Body
from app.llm.mistral_client import MistralClient
from app.models.persona import Persona
from app.core.orchestrator import ChatOrchestrator

router = APIRouter()

# Singleton for now
llm = MistralClient()
orchestrator = ChatOrchestrator()

# Register initial personas
orchestrator.register_persona(Persona(
    id="methodist",
    name="Methodist Advisor",
    system_prompt="You are a highly methodical PhD advisor who believes in structure and planning.",
    llm=llm
))

orchestrator.register_persona(Persona(
    id="theorist",
    name="Theorist Advisor",
    system_prompt="You are a philosophical PhD advisor who focuses on abstract theories and ideas.",
    llm=llm
))

orchestrator.register_persona(Persona(
    id="pragmatist",
    name="Pragmatist Advisor",
    system_prompt="You are a practical PhD advisor who focuses on real-world outcomes and utility.",
    llm=llm
))

@router.post("/chat")
async def chat(
    user_input: str = Body(...),
    active_personas: list[str] = Body(default=["methodist", "theorist", "pragmatist"])
):
    orchestrator.set_active_personas(active_personas)
    return await orchestrator.process_user_input(user_input)
