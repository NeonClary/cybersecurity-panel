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

    def get_response_order(self) ->List[str]:

        # I have created this function to be a placeholder for the actual logic of response sequencing
        # This logic can be replaced with something smarter like a LLM deciding order based on chat context

        return self.personas