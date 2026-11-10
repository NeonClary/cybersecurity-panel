"""Load BrainForge pile personas (persona2system).

The vLLM server applies a persona only when the client sends that persona's
system prompt. The private model repo is the upstream source. This module
also ships the known prompts so a public Space can use them when the repo
returns 401.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import yaml

from app.llm.neon_pile_prompts import BUNDLED_PILE_PROMPTS

logger = logging.getLogger(__name__)

_PILE_CACHE: Dict[str, Dict[str, Optional[str]]] = {}


def _bundled_personas() -> Dict[str, Optional[str]]:
    personas: Dict[str, Optional[str]] = {"vanilla": None}
    for key, prompt in BUNDLED_PILE_PROMPTS.items():
        text = (prompt or "").strip()
        if text:
            personas[str(key)] = text
    return personas


def load_pile_personas(model_name: str, revision: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Return ``{persona_id: system_prompt_or_none}`` for a BrainForge model.

    ``vanilla`` is always present with value ``None`` (no pile system prompt).
    Bundled prompts are the fallback when the model repo cannot be read.
    A successful hub download overrides the bundle for the same persona id.
    """
    cache_key = f"{model_name}@{revision or 'default'}"
    if cache_key in _PILE_CACHE:
        return _PILE_CACHE[cache_key]

    personas = _bundled_personas()
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
            if prompt:
                personas[str(key)] = prompt
        personas.setdefault("vanilla", None)
        logger.info(
            "Loaded %d pile persona(s) for %s (keys: %s)",
            len(personas),
            model_name,
            ", ".join(sorted(personas.keys())),
        )
    except EntryNotFoundError:
        logger.warning(
            "No datasets/config.yaml pile for model %s; using bundled personas %s",
            model_name,
            ", ".join(sorted(k for k in personas if k != "vanilla")),
        )
    except Exception as exc:
        logger.warning(
            "Failed to load pile personas for %s (%s); using bundled personas %s",
            model_name,
            exc,
            ", ".join(sorted(k for k in personas if k != "vanilla")),
        )

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
