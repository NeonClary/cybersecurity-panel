import httpx
import os
import json
from typing import List
from app.llm.llm_client import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, model_name: str = os.getenv("GEMINI_MODEL")):
        self.model_name = model_name
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    async def generate(self, system_prompt: str, context: List[dict]) -> str:
        # Format messages for Gemini API
        formatted_messages = []
        
        # Add system instruction
        if system_prompt:
            formatted_messages.append({
                "role": "user",
                "parts": [{"text": f"System instruction: {system_prompt}"}]
            })
            formatted_messages.append({
                "role": "model", 
                "parts": [{"text": "I understand. I'll follow these instructions in our conversation."}]
            })
        
        # Add conversation history
        for msg in context:
            role = msg['role'].lower()
            content = msg['content']
            
            if role == "user":
                formatted_messages.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role in ["methodist", "theorist", "pragmatist"]:
                # These are previous advisor responses, treat as model responses
                formatted_messages.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })
        
        payload = {
            "contents": formatted_messages,
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.9,
                "maxOutputTokens": 200,
                "stopSequences": []
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
                            
                            # Clean up common response patterns
                            text = text.replace("Here are 2-3 sentence", "").strip()
                            text = text.replace("Here's an expansion of the advice:", "").strip()
                            
                            if len(text) < 10 or text in [":", ".", ""]:
                                return "I'd be happy to help with that. Could you provide more specific details about what you're looking for?"
                            
                            return text
                
                return "I apologize, but I'm having trouble generating a response right now. Please try again."
                
        except httpx.HTTPError as e:
            return f"I apologize, but I'm having trouble connecting to generate a response. Please try again."
        except Exception as e:
            return f"I apologize, but I'm having trouble generating a response right now. Please try again."