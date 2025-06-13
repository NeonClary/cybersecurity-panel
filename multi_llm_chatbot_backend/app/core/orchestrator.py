from app.models.persona import Persona
from typing import List

class ChatOrchestrator:
    def __init__(self):
        self.personas: dict[str, Persona] = {}
        self.active_personas: List[str] = []  # renamed for clarity

    def register_persona(self, persona: Persona):
        self.personas[persona.id] = persona

    def set_active_personas(self, ids: List[str]):
        self.active_personas = [pid for pid in ids if pid in self.personas]

    def get_active_personas(self) -> List[str]:
        return self.active_personas

    async def process_user_input(self, user_input: str, context: List[dict]):
        responses = []

        for pid in self.active_personas:
            persona = self.personas[pid]
            reply = await persona.respond(context)
            responses.append({"persona": persona.name, "response": reply})
            context.append({"role": persona.id, "content": reply})

        return responses
