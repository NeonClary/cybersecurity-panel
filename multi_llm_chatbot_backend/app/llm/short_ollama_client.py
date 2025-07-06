import httpx
from typing import List
from app.llm.llm_client import LLMClient

OLLAMA_URL = "http://localhost:11434/api/generate"

# Improved LLM client with better short response handling for Ollama
class ShortResponseOllamaClient(LLMClient):
    def __init__(self, model_name: str = "llama3.2:1b"):
        self.model_name = model_name
    
    async def generate(self, system_prompt: str, context: List[dict], temperature: float, max_tokens: int) -> str:
        # Build cleaner context - only include recent relevant messages
        recent_context = context[-3:] if len(context) > 3 else context
        
        # Create a focused prompt
        prompt_parts = [system_prompt]
        
        # Add only the user's current question
        for msg in recent_context:
            if msg['role'] == 'user':
                prompt_parts.append(f"Student Question: {msg['content']}")
                break  # Only use the most recent user message
        
        prompt_parts.append("Your Response:")
        prompt = "\n\n".join(prompt_parts)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": max_tokens,  # Reduced from 200 to force shorter responses
                "repeat_penalty": 1.1,
                "stop": ["\n\n", "Student:", "Question:", "Response:"]  # Stop tokens
            }
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post("http://localhost:11434/api/generate", json=payload)
                response.raise_for_status()
                result = response.json().get("response", "[No response]").strip()
                
                # Enhanced cleanup
                result = self._clean_response(result)
                
                # Validate response quality
                if len(result) < 20 or self._is_poor_quality(result):
                    return self._get_fallback_response()
                
                return result
                
        except Exception as e:
            return "I'm having trouble generating a response right now. Please try again."
    
    def _clean_response(self, response: str) -> str:
        """Clean up common response issues"""
        # Remove common prefixes
        prefixes_to_remove = [
            "Here are 2-3 sentence", "Here's an expansion", "Assistant:",
            "Dr. Methodist:", "Dr. Theorist:", "Dr. Pragmatist:",
            "Methodist Advisor:", "Theorist Advisor:", "Pragmatist Advisor:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Remove trailing incomplete sentences
        sentences = response.split('.')
        if len(sentences) > 1 and len(sentences[-1].strip()) < 10:
            response = '.'.join(sentences[:-1]) + '.'
        
        # Remove excessive academic fluff
        fluff_patterns = [
            "conceptual insights:", "actionable advice:", "my inquisitive student",
            "excellent question", "thank you for", "assistant!"
        ]
        
        for pattern in fluff_patterns:
            response = response.replace(pattern, "").strip()
        
        return response
    
    def _is_poor_quality(self, response: str) -> bool:
        """Check if response quality is poor"""
        poor_indicators = [
            "Thank you, Dr." in response,  # AI confusion about identity
            "Assistant:" in response,
            len(response.split()) > 100,  # Too verbose
            response.count("?") > 3,  # Too many questions
        ]
        return any(poor_indicators)
    
    def _get_fallback_response(self) -> str:
        """Return a simple fallback when quality is poor"""
        return "I'd be happy to help with that. Could you provide more specific details about what you're looking for?"