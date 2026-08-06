"""API/model health pre-check using each client's real generate() path."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROBE_PROMPT = "Reply with the single word: OK"
PROBE_MAX_TOKENS = 16
PROBE_TEMPERATURE = 0.0
CACHE_TTL_SECONDS = 45
ERROR_MESSAGE_MAX_CHARS = 200

# Soft-fail strings returned by LLM clients instead of raising.
_FAILURE_MARKERS = (
    "unable to connect",
    "encountered an error",
    "unexpected error",
    "experiencing issues connecting",
    "taking too long to respond",
    "couldn't generate a meaningful response",
    "unable to generate a response",
    "unexpected response format",
    "please ensure ollama is running",
    "please ensure the vllm endpoint",
    "openai returned empty content",
    "openai api key not set",
    "gemini api key not set",
    "no vllm endpoint configured",
)

_cache: Optional[Dict[str, Any]] = None
_cache_mono: float = 0.0


def truncate_error(message: str, limit: int = ERROR_MESSAGE_MAX_CHARS) -> str:
    text = (message or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def classify_probe_text(text: Optional[str]) -> Tuple[str, Optional[str]]:
    """Classify a probe response body.

    Returns ``(status, error_snippet)`` where status is one of
    ``online``, ``unavailable``, or ``error``.
    """
    if text is None:
        return "unavailable", None
    stripped = text.strip()
    if not stripped:
        return "unavailable", None
    lower = stripped.lower()
    if any(marker in lower for marker in _FAILURE_MARKERS):
        return "error", truncate_error(stripped)
    return "online", None


def classify_probe_exception(exc: BaseException) -> Tuple[str, str]:
    return "error", truncate_error(str(exc) or exc.__class__.__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_probe_targets() -> List[Dict[str, Any]]:
    """Describe configured providers/APIs to probe (no secrets in output)."""
    from app.config import get_settings
    from app.core import bootstrap as boot
    from app.llm.improved_gemini_client import ImprovedGeminiClient
    from app.llm.improved_ollama_client import ImprovedOllamaClient
    from app.llm.openai_fallback_client import OpenAIFallbackClient

    settings = get_settings()
    targets: List[Dict[str, Any]] = []

    # vLLM — direct primary (not the resilient wrapper)
    if settings.llm.vllm.api_url:
        try:
            neon = settings.llm.vllm.neon_persona_orchestrator
            client = boot._build_neon_vllm(neon if neon != "vanilla" else None)
            targets.append({
                "id": "vllm",
                "name": "vLLM",
                "provider": "vllm",
                "model": getattr(client, "model_name", None) or settings.llm.vllm.model_id or "",
                "selectable": True,
                "client": client,
            })
        except Exception as exc:
            targets.append({
                "id": "vllm",
                "name": "vLLM",
                "provider": "vllm",
                "model": settings.llm.vllm.model_id or "",
                "selectable": True,
                "client": None,
                "build_error": exc,
            })
    else:
        targets.append({
            "id": "vllm",
            "name": "vLLM",
            "provider": "vllm",
            "model": settings.llm.vllm.model_id or "",
            "selectable": True,
            "client": None,
            "build_error": ValueError("No vLLM endpoint configured"),
        })

    # OpenAI fallback — configured when an API key is available
    openai_key = boot._openai_api_key()
    if openai_key:
        try:
            client = OpenAIFallbackClient(
                api_key=openai_key,
                model=settings.llm.openai.model,
                reasoning_effort="none",
            )
            targets.append({
                "id": "openai",
                "name": "OpenAI",
                "provider": "openai",
                "model": settings.llm.openai.model,
                "selectable": False,
                "client": client,
            })
        except Exception as exc:
            targets.append({
                "id": "openai",
                "name": "OpenAI",
                "provider": "openai",
                "model": settings.llm.openai.model,
                "selectable": False,
                "client": None,
                "build_error": exc,
            })

    # Gemini
    if settings.llm.gemini.api_key:
        try:
            client = ImprovedGeminiClient(model_name=settings.llm.gemini.model)
            targets.append({
                "id": "gemini",
                "name": "Gemini",
                "provider": "gemini",
                "model": settings.llm.gemini.model,
                "selectable": True,
                "client": client,
            })
        except Exception as exc:
            targets.append({
                "id": "gemini",
                "name": "Gemini",
                "provider": "gemini",
                "model": settings.llm.gemini.model,
                "selectable": True,
                "client": None,
                "build_error": exc,
            })
    else:
        targets.append({
            "id": "gemini",
            "name": "Gemini",
            "provider": "gemini",
            "model": settings.llm.gemini.model,
            "selectable": True,
            "client": None,
            "build_error": ValueError("Gemini API key not set"),
        })

    # Ollama — always considered configured (local endpoint)
    try:
        client = ImprovedOllamaClient(
            model_name=settings.llm.ollama.model,
            base_url=settings.llm.ollama.base_url,
        )
        targets.append({
            "id": "ollama",
            "name": "Ollama",
            "provider": "ollama",
            "model": settings.llm.ollama.model,
            "selectable": True,
            "client": client,
        })
    except Exception as exc:
        targets.append({
            "id": "ollama",
            "name": "Ollama",
            "provider": "ollama",
            "model": settings.llm.ollama.model,
            "selectable": True,
            "client": None,
            "build_error": exc,
        })

    return targets


async def _probe_one(target: Dict[str, Any]) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "id": target["id"],
        "name": target["name"],
        "provider": target["provider"],
        "model": target.get("model") or "",
        "selectable": bool(target.get("selectable")),
        "status": "error",
        "error": None,
        "latency_ms": None,
    }

    build_error = target.get("build_error")
    if build_error is not None:
        status, err = classify_probe_exception(build_error)
        entry["status"] = status
        entry["error"] = err
        return entry

    client = target.get("client")
    if client is None:
        entry["status"] = "unavailable"
        return entry

    started = time.monotonic()
    try:
        text = await client.generate(
            system_prompt="",
            context=[{"role": "user", "content": PROBE_PROMPT}],
            temperature=PROBE_TEMPERATURE,
            max_tokens=PROBE_MAX_TOKENS,
        )
        status, err = classify_probe_text(text if isinstance(text, str) else None)
        entry["status"] = status
        entry["error"] = err
    except Exception as exc:
        logger.warning("Model probe failed for %s: %s", target["id"], exc)
        status, err = classify_probe_exception(exc)
        entry["status"] = status
        entry["error"] = err
    finally:
        entry["latency_ms"] = int((time.monotonic() - started) * 1000)

    return entry


async def _probe_all() -> Dict[str, Any]:
    targets = _build_probe_targets()
    results = await asyncio.gather(*[_probe_one(t) for t in targets])
    models = list(results)
    online_providers = sorted(
        m["id"]
        for m in models
        if m.get("selectable") and m.get("status") == "online"
    )
    return {
        "models": models,
        "online_providers": online_providers,
        "checked_at": _iso_now(),
        "check_failed": False,
    }


async def get_model_status(*, force_refresh: bool = False) -> Dict[str, Any]:
    """Return cached or freshly probed model statuses.

    Fail-open behavior is applied by the route when this raises: the caller
    should keep the unfiltered provider list. Per-model failures are fail-closed
    (status != online) inside ``_probe_all``.
    """
    global _cache, _cache_mono

    if (
        not force_refresh
        and _cache is not None
        and (time.monotonic() - _cache_mono) < CACHE_TTL_SECONDS
    ):
        return {**_cache, "cached": True}

    result = await _probe_all()
    _cache = result
    _cache_mono = time.monotonic()
    return {**result, "cached": False}


def clear_model_status_cache() -> None:
    """Test helper to drop the in-process probe cache."""
    global _cache, _cache_mono
    _cache = None
    _cache_mono = 0.0
