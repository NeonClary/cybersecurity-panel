from fastapi import APIRouter, Body, HTTPException, Query
from app.models.default_personas import get_default_personas
from app.core import bootstrap
from app.core.bootstrap import chat_orchestrator
from app.core.model_status import get_model_status
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ProviderSwitch(BaseModel):
    provider: str


def _model_name(client) -> str:
    name = getattr(client, "model_name", None)
    if not name:
        # ResilientLLMClient wraps the primary client
        primary = getattr(client, "primary", None)
        name = getattr(primary, "model_name", None)
    return name or "unknown"


@router.get("/current-provider")
async def get_current_provider():
    return {
        "current_provider": bootstrap.current_provider,
        "available_providers": bootstrap.available_providers,
        "model_info": {
            "name": _model_name(bootstrap.llm),
            "provider": bootstrap.current_provider,
        },
    }


@router.post("/switch-provider")
async def switch_provider(provider_data: ProviderSwitch):
    if provider_data.provider not in bootstrap.available_providers:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown provider: {provider_data.provider}. "
                f"Available: {bootstrap.available_providers}"
            ),
        )

    # Fail closed (plan §10): refuse to switch to a provider whose health
    # probe says it is not online. If the probe itself fails, fail open so a
    # broken status checker can't lock the user out of switching.
    try:
        payload = await get_model_status(force_refresh=False)
        entry = next(
            (
                m for m in (payload.get("models") or [])
                if m.get("provider") == provider_data.provider
            ),
            None,
        )
        if entry and entry.get("status") != "online":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Provider '{provider_data.provider}' is "
                    f"{entry.get('status', 'unavailable')} right now; refusing to switch. "
                    "Refresh Model Status and try again."
                ),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Provider health gate skipped (probe failed): %s", exc)

    previous = bootstrap.current_provider
    try:
        bootstrap.set_current_provider(provider_data.provider)
        new_llm = bootstrap.create_orchestrator_llm()
        bootstrap.llm = new_llm
        chat_orchestrator.llm_client = new_llm

        persona_llm = bootstrap.create_persona_llm()
        new_personas = get_default_personas(persona_llm)
        chat_orchestrator.personas.clear()
        for persona in new_personas:
            chat_orchestrator.register_persona(persona)

        return {
            "message": f"Successfully switched to {bootstrap.current_provider}",
            "current_provider": bootstrap.current_provider,
            "model_info": {
                "name": _model_name(new_llm),
                "provider": bootstrap.current_provider,
            },
        }

    except Exception as e:
        bootstrap.set_current_provider(previous)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch to {provider_data.provider}: {str(e)}",
        )


@router.post("/switch-model")
async def switch_model(model_name: str = Body(...)):
    if "gemini" in model_name.lower():
        return await switch_provider(ProviderSwitch(provider="gemini"))
    else:
        return await switch_provider(ProviderSwitch(provider="ollama"))


@router.get("/current-model")
async def get_current_model():
    return {
        "model": _model_name(bootstrap.llm),
        "provider": bootstrap.current_provider,
    }


@router.get("/models/status")
async def models_status(refresh: bool = Query(False, description="Bypass short-lived probe cache")):
    """Probe configured LLM APIs using the same generate() path as chat traffic.

    Returns per-model status (online / unavailable / error). On total probe
    failure, returns ``check_failed: true`` so the UI can fail open
    (keep the unfiltered provider list).
    """
    try:
        return await get_model_status(force_refresh=refresh)
    except Exception as exc:
        logger.warning("Model status check failed entirely: %s", exc)
        return {
            "models": [],
            "online_providers": None,
            "checked_at": None,
            "cached": False,
            "check_failed": True,
            "error": str(exc)[:200],
        }
