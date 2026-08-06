"""Load Security Journey track definitions from YAML under ``tracks/``."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from app.models.journey import Track, TrackItem, TrackLevel, TrackSummary

LOG = logging.getLogger(__name__)

_tracks_cache: Optional[Dict[str, Track]] = None


def resolve_tracks_dir() -> Path:
    """Locate the ``tracks/`` directory.

    Resolution order:
    1. ``TRACKS_DIR`` env var (absolute or relative)
    2. Sibling of ``CONFIG_PATH``'s parent (``<config_dir>/tracks``)
    3. ``./tracks`` relative to the process cwd
    4. Walk parents of this file looking for a ``tracks`` folder
    """
    env = os.getenv("TRACKS_DIR")
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p.resolve()
        LOG.warning("TRACKS_DIR=%s is not a directory; falling back", env)

    config_path = os.getenv("CONFIG_PATH")
    if config_path:
        candidate = Path(config_path).expanduser().resolve().parent / "tracks"
        if candidate.is_dir():
            return candidate

    cwd_candidate = Path.cwd() / "tracks"
    if cwd_candidate.is_dir():
        return cwd_candidate.resolve()

    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "tracks"
        if candidate.is_dir():
            return candidate

    # Last resort: expected deploy layout next to config
    if config_path:
        return Path(config_path).expanduser().resolve().parent / "tracks"
    return Path.cwd() / "tracks"


def _parse_track(raw: dict) -> Track:
    levels_raw = raw.get("levels") or raw.get("stages") or []
    levels: List[TrackLevel] = []
    for lvl in levels_raw:
        items = [
            TrackItem(
                id=str(it["id"]),
                title=str(it.get("title") or it["id"]),
                description=str(it.get("description") or ""),
            )
            for it in (lvl.get("items") or [])
            if it.get("id")
        ]
        levels.append(
            TrackLevel(
                id=str(lvl["id"]),
                name=str(lvl.get("name") or lvl["id"]),
                description=str(lvl.get("description") or ""),
                items=items,
            )
        )
    audience = raw.get("audience") or "any"
    if audience not in ("individual", "smb", "enterprise", "any"):
        audience = "any"
    return Track(
        id=str(raw["id"]),
        name=str(raw.get("name") or raw["id"]),
        description=str(raw.get("description") or "").strip(),
        audience=audience,
        levels=levels,
    )


def load_tracks(force_reload: bool = False) -> Dict[str, Track]:
    """Return all tracks keyed by id. Cached after first successful load."""
    global _tracks_cache
    if _tracks_cache is not None and not force_reload:
        return _tracks_cache

    tracks_dir = resolve_tracks_dir()
    loaded: Dict[str, Track] = {}

    if not tracks_dir.is_dir():
        LOG.warning("Tracks directory not found at %s", tracks_dir)
        _tracks_cache = loaded
        return loaded

    for path in sorted(tracks_dir.glob("*.yaml")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            if not raw.get("id"):
                LOG.warning("Skipping track file without id: %s", path)
                continue
            track = _parse_track(raw)
            loaded[track.id] = track
            LOG.info("Loaded journey track %s (%d levels) from %s", track.id, len(track.levels), path.name)
        except Exception as exc:
            LOG.error("Failed to load track %s: %s", path, exc)

    _tracks_cache = loaded
    return loaded


def get_track(track_id: str) -> Optional[Track]:
    return load_tracks().get(track_id)


def list_track_summaries() -> List[TrackSummary]:
    summaries: List[TrackSummary] = []
    for track in load_tracks().values():
        item_count = sum(len(lvl.items) for lvl in track.levels)
        summaries.append(
            TrackSummary(
                id=track.id,
                name=track.name,
                description=track.description,
                audience=track.audience,
                level_count=len(track.levels),
                item_count=item_count,
            )
        )
    return summaries


def compute_progress(track: Optional[Track], checked_item_ids: List[str]):
    """Return (level_id, level_name, level_index, level_count, pct_overall, pct_in_level).

    Current level is the first level that still has unchecked items, or the
    last level when everything is complete. Progress within a level is the
    fraction of that level's items that are checked.
    """
    if not track or not track.levels:
        return None, None, 0, 0, 0.0, 0.0

    checked = set(checked_item_ids or [])
    all_ids = [it.id for lvl in track.levels for it in lvl.items]
    pct_overall = (len(checked & set(all_ids)) / len(all_ids) * 100.0) if all_ids else 0.0

    level_count = len(track.levels)
    current_idx = level_count - 1
    for i, lvl in enumerate(track.levels):
        lvl_ids = [it.id for it in lvl.items]
        if not lvl_ids or any(iid not in checked for iid in lvl_ids):
            current_idx = i
            break

    current = track.levels[current_idx]
    lvl_ids = [it.id for it in current.items]
    done_in_level = sum(1 for iid in lvl_ids if iid in checked)
    pct_in_level = (done_in_level / len(lvl_ids) * 100.0) if lvl_ids else 100.0

    return (
        current.id,
        current.name,
        current_idx,
        level_count,
        round(pct_overall, 1),
        round(pct_in_level, 1),
    )


def clear_tracks_cache() -> None:
    global _tracks_cache
    _tracks_cache = None
