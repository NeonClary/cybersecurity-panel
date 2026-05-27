"""Return the current date and time for orchestrator context."""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_current_datetime",
        "description": (
            "Get the current date and time in UTC and in a configured local timezone. "
            "Use when the user asks about today, deadlines, timelines, schedules, "
            "or when accurate temporal context improves security guidance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "IANA timezone name (e.g. America/Los_Angeles). "
                        "Optional; defaults to the app-configured timezone."
                    ),
                },
            },
            "required": [],
        },
    },
}


async def execute(name: str = "", timezone: str | None = None, **_: Any) -> Dict[str, Any]:
    from app.config import get_settings

    cfg = get_settings().tools.get_tool_config("current_datetime")
    tz_name = timezone or cfg.get("default_timezone") or "UTC"
    tz = dt_timezone.utc
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz_name = "UTC"
            tz = dt_timezone.utc

    now_utc = datetime.now(dt_timezone.utc)
    now_local = now_utc.astimezone(tz)

    return {
        "utc_iso": now_utc.isoformat(),
        "local_iso": now_local.isoformat(),
        "local_timezone": tz_name,
        "local_weekday": now_local.strftime("%A"),
        "local_date": now_local.strftime("%Y-%m-%d"),
        "local_time": now_local.strftime("%H:%M:%S"),
    }
