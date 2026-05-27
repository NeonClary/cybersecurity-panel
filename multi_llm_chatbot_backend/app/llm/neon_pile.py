"""Load BrainForge pile personas (persona2system) from a HuggingFace model repo."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Dict, Optional

import yaml

logger = logging.getLogger(__name__)

_PILE_CACHE: Dict[str, Dict[str, Optional[str]]] = {}


def load_pile_personas(model_name: str, revision: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Return ``{persona_id: system_prompt_or_none}`` for a BrainForge model.

    ``vanilla`` is always present with value ``None`` (no pile system prompt).
    """
    cache_key = f"{model_name}@{revision or 'default'}"
    if cache_key in _PILE_CACHE:
        return _PILE_CACHE[cache_key]

    personas: Dict[str, Optional[str]] = {"vanilla": None}
    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.utils import EntryNotFoundError

        config_path = hf_hub_download(
            model_name,
            "config.yaml",
            subfolder="datasets",
            revision=revision,
        )
        with open(config_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        pile = data.get("pile") or {}
        persona2system = pile.get("persona2system") or {}
        for key, prompt in persona2system.items():
            personas[str(key)] = prompt
        personas.setdefault("vanilla", None)
        logger.info(
            "Loaded %d pile persona(s) for %s (keys: %s)",
            len(personas),
            model_name,
            ", ".join(sorted(personas.keys())),
        )
    except EntryNotFoundError:
        logger.warning("No datasets/config.yaml pile for model %s", model_name)
    except Exception as exc:
        logger.warning("Failed to load pile personas for %s: %s", model_name, exc)

    _PILE_CACHE[cache_key] = personas
    return personas


def get_pile_system_prompt(
    model_name: str,
    neon_persona: Optional[str],
    revision: Optional[str] = None,
) -> Optional[str]:
    """Resolve a pile system prompt for *neon_persona*, or None for vanilla/missing."""
    if not neon_persona or neon_persona == "vanilla":
        return None
    pile = load_pile_personas(model_name, revision=revision)
    return pile.get(neon_persona)
