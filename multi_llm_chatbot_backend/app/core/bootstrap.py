# app/core/bootstrap.py
import os
from app.llm.improved_gemini_client import ImprovedGeminiClient
from app.llm.improved_ollama_client import ImprovedOllamaClient
from app.core.improved_orchestrator import ImprovedChatOrchestrator
from app.models.default_personas import get_default_personas

current_provider = "gemini"
available_providers = ["ollama", "gemini"]

def create_llm_client(provider=None):
    if provider is None:
        provider = current_provider
    if provider == "gemini":
        return ImprovedGeminiClient(model_name=os.getenv("GEMINI_MODEL"))
    else:
        return ImprovedOllamaClient(model_name="llama3.2:1b")

llm = create_llm_client()
chat_orchestrator = ImprovedChatOrchestrator()

DEFAULT_PERSONAS = get_default_personas(llm)
for persona in DEFAULT_PERSONAS:
    chat_orchestrator.register_persona(persona)
