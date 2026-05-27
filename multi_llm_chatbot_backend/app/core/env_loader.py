"""Load local and shared environment files before LLM bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _shared_env_paths() -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get("SHARED_ENV", "").strip()
    if explicit:
        paths.append(Path(explicit))
    paths.append(Path.home() / ".secrets" / "shared.env")
    return paths


def load_application_env() -> None:
    """Load cwd .env, backend .env, then shared secrets (without overriding explicit env)."""
    load_dotenv()
    backend_env = _BACKEND_ROOT / ".env"
    if backend_env.is_file():
        load_dotenv(backend_env, override=False)
    for path in _shared_env_paths():
        if path.is_file():
            load_dotenv(path, override=False)
            return
