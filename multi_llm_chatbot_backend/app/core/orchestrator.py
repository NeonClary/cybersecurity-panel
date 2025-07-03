from app.models.persona import Persona
from typing import List
from app.utils.chroma_client import query_persona_knowledge
from app.llm.gemini_client import GeminiClient
from app.llm.llm_client import LLMClient

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
    
async def answer_with_persona_context(question: str, persona: str) -> str:
    llm: LLMClient = GeminiClient()
    context_chunks = query_persona_knowledge(question, persona)
    context = "\n".join(context_chunks) if context_chunks else "No relevant info found."
        
    system_prompt = f"You are a helpful assistant responding as a {persona}."
    message_context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{question}"}
    ]

    return await llm.generate(system_prompt, message_context)