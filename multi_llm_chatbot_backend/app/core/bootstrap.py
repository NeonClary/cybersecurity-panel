# app/core/bootstrap.py
import os
from pathlib import Path

from app.core.env_loader import load_application_env

load_application_env()

from app.config import get_settings
from app.llm.improved_gemini_client import ImprovedGeminiClient
from app.llm.improved_ollama_client import ImprovedOllamaClient
from app.llm.improved_vllm_client import ImprovedVllmClient
from app.llm.openai_fallback_client import OpenAIFallbackClient
from app.llm.resilient_client import ResilientLLMClient
from app.core.improved_orchestrator import ImprovedChatOrchestrator
from app.models.default_personas import get_default_personas

settings = get_settings()

current_provider = settings.llm.provider or "vllm"
available_providers = ["ollama", "gemini", "vllm"]


def _load_shared_env_var(name: str) -> str:
    explicit = os.environ.get("SHARED_ENV", "").strip()
    candidates = [Path(explicit)] if explicit else []
    candidates.append(Path.home() / ".secrets" / "shared.env")
    prefix = f"{name}="
    for shared in candidates:
        if not shared.is_file():
            continue
        for line in shared.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(prefix):
                return line.split("=", 1)[1].strip()
    return ""


def _vllm_api_username() -> str:
    """Optional HTTP Basic auth username for the vLLM endpoint.

    The Neon BrainForge/Security endpoint at 4090-x1-3 requires HTTP Basic
    auth using HANA_USERNAME_KLATCHAT / HANA_KLATCHAT_PASSWORD from
    ~/.secrets/shared.env. We allow explicit override via api_username
    in config or VLLM_API_USERNAME env var, falling back to the shared
    HANA_USERNAME_KLATCHAT entry.
    """
    return (
        settings.llm.vllm.api_username
        or os.getenv("VLLM_API_USERNAME", "")
        or _load_shared_env_var("HANA_USERNAME_KLATCHAT")
    )


def _vllm_api_key() -> str:
    """vLLM key/password. If api_username is set (HANA Basic auth), prefer
    HANA_KLATCHAT_PASSWORD; otherwise use the generic VLLM_API_KEY Bearer
    token. This matches the dual-auth nature of the Neon endpoints.
    """
    if _vllm_api_username():
        return (
            settings.llm.vllm.api_key
            or os.getenv("HANA_KLATCHAT_PASSWORD", "")
            or _load_shared_env_var("HANA_KLATCHAT_PASSWORD")
            or os.getenv("VLLM_API_KEY", "")
            or _load_shared_env_var("VLLM_API_KEY")
        )
    return (
        settings.llm.vllm.api_key
        or os.getenv("VLLM_API_KEY", "")
        or _load_shared_env_var("VLLM_API_KEY")
    )


def _openai_api_key() -> str:
    return (
        settings.llm.openai.api_key
        or os.getenv("OPENAI_API_KEY", "")
        or _load_shared_env_var("OPENAI_API_KEY")
    )


def _build_neon_vllm(neon_persona: str | None) -> ImprovedVllmClient:
    vllm = settings.llm.vllm
    if not vllm.api_url:
        raise ValueError("No vLLM endpoint configured. Set llm.vllm.api_url in your config.")
    model_name = vllm.model_id or None
    return ImprovedVllmClient(
        api_url=vllm.api_url,
        api_key=_vllm_api_key(),
        model_name=model_name,
        neon_persona=neon_persona,
        api_username=_vllm_api_username() or None,
    )


def _build_openai(reasoning_effort: str) -> OpenAIFallbackClient:
    return OpenAIFallbackClient(
        api_key=_openai_api_key(),
        model=settings.llm.openai.model,
        reasoning_effort=reasoning_effort,
    )


def _wrap_resilient(primary: ImprovedVllmClient, fallback: OpenAIFallbackClient, label: str):
    return ResilientLLMClient(
        primary=primary,
        fallback=fallback,
        race_timeout_seconds=settings.llm.resilient.race_timeout_seconds,
        primary_label=label,
    )


def create_llm_client(provider=None):
    if provider is None:
        provider = current_provider
    if provider == "gemini":
        return ImprovedGeminiClient(model_name=settings.llm.gemini.model)
    if provider == "vllm":
        neon = settings.llm.vllm.neon_persona_orchestrator
        primary = _build_neon_vllm(neon if neon != "vanilla" else None)
        fallback = _build_openai(settings.llm.openai.orchestrator_reasoning_effort)
        return _wrap_resilient(primary, fallback, "orchestrator")
    return ImprovedOllamaClient(
        model_name=settings.llm.ollama.model,
        base_url=settings.llm.ollama.base_url,
    )


def create_orchestrator_llm():
    if current_provider != "vllm":
        return create_llm_client()
    neon = settings.llm.vllm.neon_persona_orchestrator
    primary = _build_neon_vllm(neon if neon != "vanilla" else None)
    fallback = _build_openai(settings.llm.openai.orchestrator_reasoning_effort)
    return _wrap_resilient(primary, fallback, "orchestrator")


def create_persona_llm():
    if current_provider != "vllm":
        return create_llm_client()
    neon = settings.llm.vllm.neon_persona_advisors
    primary = _build_neon_vllm(neon)
    fallback = _build_openai(settings.llm.openai.persona_reasoning_effort)
    return _wrap_resilient(primary, fallback, "persona")


llm = create_orchestrator_llm()
chat_orchestrator = ImprovedChatOrchestrator(llm_client=llm)

persona_llm = create_persona_llm() if current_provider == "vllm" else llm
DEFAULT_PERSONAS = get_default_personas(persona_llm)
for persona in DEFAULT_PERSONAS:
    chat_orchestrator.register_persona(persona)
