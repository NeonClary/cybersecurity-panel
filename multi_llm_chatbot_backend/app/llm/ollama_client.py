import httpx
from typing import List
from app.llm.llm_client import LLMClient

OLLAMA_URL = "http://localhost:11434/api/generate"

class OllamaClient(LLMClient):
    def __init__(self, model_name: str = "llama3.2:1b"):
        self.model_name = model_name
    
    async def generate(self, system_prompt: str, context: List[dict], temperature: float, max_tokens: int) -> str:
        # Flatten context into a string
        formatted = "\n".join(f"{msg['role'].capitalize()}: {msg['content']}" for msg in context)
        full_prompt = f"{system_prompt}\n\n{formatted}\n\nAssistant:"
        
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": max_tokens,  # Limit response length for faster generation
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # Reduced timeout
                response = await client.post(OLLAMA_URL, json=payload)
                response.raise_for_status()
                return response.json().get("response", "[No response]")
        except httpx.HTTPError as e:
            return f"[Error from {self.model_name}: {str(e)}]"