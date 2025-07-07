import httpx
import os
from typing import List
from app.llm.llm_client import LLMClient
from app.core.context_manager import get_context_manager
import logging

logger = logging.getLogger(__name__)

class ImprovedGeminiClient(LLMClient):
    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        
        self.model_name = model_name
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.context_manager = get_context_manager()
    
    async def generate(self, system_prompt: str, context: List[dict], temperature: float, max_tokens: int) -> str:
        """
        Generate response using improved context management
        """
        try:
            # Use context manager to prepare optimal context window
            context_window = self.context_manager.prepare_context_for_llm(
                messages=context,
                system_prompt=system_prompt,
                llm_provider="gemini"
            )
            
            logger.debug(f"Context prepared: {len(context_window.messages)} messages, "
                        f"~{context_window.total_tokens} tokens, truncated={context_window.truncated}")
            
            payload = {
                "contents": context_window.messages,
                "generationConfig": {
                    "temperature": temperature,
                    "topK": 40,
                    "topP": 0.9,
                    "maxOutputTokens": max_tokens,
                    "stopSequences": ["Student:", "Question:", "\n\nStudent:", "\n\nQuestion:"]
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
            }
            
            url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                if "candidates" in result and result["candidates"]:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        text = candidate["content"]["parts"][0].get("text", "")
                        return self._clean_response(text)
                
                # Handle safety filter or other issues
                if "promptFeedback" in result:
                    feedback = result["promptFeedback"]
                    logger.warning(f"Gemini prompt feedback: {feedback}")
                
                return "I apologize, but I'm unable to provide a response to that query."
                
        except httpx.TimeoutException:
            logger.error("Gemini API timeout")
            return "I'm experiencing a delay in processing. Please try again."
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API HTTP error: {e.response.status_code} - {e.response.text}")
            return "I'm having trouble accessing the AI service. Please try again."
        except Exception as e:
            logger.error(f"Unexpected error in Gemini client: {str(e)}")
            return "I encountered an unexpected error. Please try again."
    
    def _clean_response(self, response: str) -> str:
        """Clean up response text"""
        # Remove common issues
        response = response.strip()
        
        # Remove duplicate spaces and normalize
        response = ' '.join(response.split())
        
        return response