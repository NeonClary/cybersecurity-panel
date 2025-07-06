import httpx
import os
from typing import List
from app.llm.llm_client import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        
        self.model_name = model_name
        self.api_key = os.getenv("GEMINI_API_KEY")
        print("DEBUG: GEMINI_API_KEY =", os.getenv("GEMINI_API_KEY"))
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    async def generate(self, system_prompt: str, context: List[dict], temperature: float, max_tokens: int) -> str:
        # Build focused context - only include recent relevant messages
        recent_context = context[-3:] if len(context) > 3 else context
        
        # Format messages for Gemini API
        formatted_messages = []
        
        # Add system instruction as initial conversation
        if system_prompt:
            formatted_messages.append({
                "role": "user",
                "parts": [{"text": system_prompt}]
            })
            formatted_messages.append({
                "role": "model", 
                "parts": [{"text": "I understand. I'll follow these instructions."}]
            })
        
        # Add only the user's current question
        for msg in recent_context:
            if msg['role'] == 'user':
                formatted_messages.append({
                    "role": "user",
                    "parts": [{"text": msg['content']}]
                })
                break  # Only use most recent user message
        
        payload = {
            "contents": formatted_messages,
            "generationConfig": {
                "temperature": temperature,
                "topK": 40,
                "topP": 0.9,
                "maxOutputTokens": max_tokens,  # Reduced from default to ensure concise responses
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

        try:
            url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                # Extract text from Gemini response
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]
                        if len(parts) > 0 and "text" in parts[0]:
                            text = parts[0]["text"].strip()
                            
                            # Clean up response
                            text = self._clean_response(text)
                            
                            # Validate response quality
                            if len(text) < 20 or self._is_poor_quality(text):
                                print("Poor Response Quality from Gemini")
                                return self._get_fallback_response()
                            
                            return text
                
                print("Candidate Issue")
                return self._get_fallback_response()
                
        except httpx.HTTPError as e:
            print(f"HTTP error calling Gemini API: {e}")
            return "I'm having trouble connecting to generate a response. Please try again."
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return "I'm having trouble generating a response right now. Please try again."
    
    def _clean_response(self, response: str) -> str:
        """Clean up Gemini responses"""
        # Remove common prefixes that indicate AI confusion
        prefixes_to_remove = [
            "Dr. Methodist:", "Dr. Theorist:", "Dr. Pragmatist:",
            "Methodist Advisor:", "Theorist Advisor:", "Pragmatist Advisor:",
            "As Dr.", "Here's my response:", "Response:", "Assistant:",
            "Here are 2-3 sentence", "Here's an expansion of the advice:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Remove excessive academic fluff
        fluff_patterns = [
            "conceptual insights:", "actionable advice:", "my inquisitive student",
            "excellent question", "thank you for", "assistant!", "excellent discussion"
        ]
        
        for pattern in fluff_patterns:
            response = response.replace(pattern, "").strip()
        
        # Remove trailing incomplete sentences
        sentences = response.split('.')
        if len(sentences) > 1 and len(sentences[-1].strip()) < 10:
            response = '.'.join(sentences[:-1]) + '.'
        
        return response
    
    def _is_poor_quality(self, response: str) -> bool:
        """Check if response quality is poor"""
        poor_indicators = [
            "Thank you, Dr." in response,  # AI confusion about identity
            "Assistant:" in response,
            len(response.split()) > 700,  # Too verbose
            response.count("?") > 3,  # Too many questions
            "excellent discussion, Assistant" in response,
        ]
        return any(poor_indicators)
    
    def _get_fallback_response(self) -> str:
        """Return a simple fallback when quality is poor"""
        return "I'd be happy to help with that. Could you provide more specific details about what you're looking for?"