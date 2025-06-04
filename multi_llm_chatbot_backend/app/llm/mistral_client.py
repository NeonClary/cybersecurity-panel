import httpx
from typing import List
from app.llm.llm_client import LLMClient

OLLAMA_URL = "http://localhost:11434/api/generate"

class MistralClient(LLMClient):
    async def generate(self, system_prompt: str, context: List[dict]) -> str:
        # Flatten context into a string
        formatted = "\n".join(f"{msg['role'].capitalize()}: {msg['content']}" for msg in context)
        full_prompt = f"{system_prompt}\n\n{formatted}\n\nAssistant:"
        
        payload = {
            "model": "mistral",
            "prompt": full_prompt,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(OLLAMA_URL, json=payload)
                response.raise_for_status()
                return response.json().get("response", "[No response]")
        except httpx.HTTPError as e:
            return f"[Error from Mistral: {str(e)}]"
