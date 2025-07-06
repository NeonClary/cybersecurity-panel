from app.llm.llm_client import LLMClient

class Persona:
    def __init__(self, id, name, system_prompt, llm, temperature=5):
        self.id = id
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm
        self.temperature = temperature
    
    async def respond(self, context: list[dict], response_length: str = "medium") -> str:
        max_tokens_map = {
            "short": 200,
            "medium": 300,
            "long": 500
        }

        response_style_map = {
            "short": "Please keep your response concise (1-3 sentences).",
            "medium": "Please provide a moderately detailed explanation (5-7 sentences).",
            "long": "Provide a thorough and in-depth explanation (9+ sentences)."
        }

        max_tokens = max_tokens_map.get(response_length, 300)
        response_instruction = response_style_map.get(response_length, "medium")
        temp_scaled = round(self.temperature / 10, 2)

        full_prompt = f"{self.system_prompt}\n\n{response_instruction}"

        return await self.llm.generate(
            system_prompt=full_prompt,
            context=context,
            temperature=temp_scaled,
            max_tokens=max_tokens
        )

