from fastapi import APIRouter

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
def root():
    return {
        "message": "Multi-LLM PhD Advisor Backend is up and running",
        "version": "1.0.0",
        "features": [
            "Improved Session Management",
            "Unified Context Handling",
            "Ollama Support",
            "Gemini API Support",
            "Provider Switching"
        ]
    }

