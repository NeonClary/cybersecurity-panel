from app.models.persona import Persona

class ChatOrchestrator:
    def __init__(self):
        self.history: list[dict] = []
        self.personas: dict[str, Persona] = {}

    def register_persona(self, persona: Persona):
        self.personas[persona.id] = persona

    def set_active_personas(self, ids: list[str]):
        self.active_ids = [pid for pid in ids if pid in self.personas]

    async def process_user_input(self, user_input: str):
        self.history.append({"role": "user", "content": user_input})
        responses = []

        for pid in self.active_ids:
            persona = self.personas[pid]
            reply = await persona.respond(self.history)
            self.history.append({"role": persona.id, "content": reply})
            responses.append({"persona": persona.name, "response": reply})

        return responses
