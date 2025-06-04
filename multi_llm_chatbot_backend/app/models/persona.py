from app.llm.llm_client import LLMClient

class Persona:
    def __init__(self, id: str, name: str, system_prompt: str, llm: LLMClient):
        self.id = id
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm

    async def respond(self, context: list[dict]) -> str:
        return await self.llm.generate(self.system_prompt, context)
