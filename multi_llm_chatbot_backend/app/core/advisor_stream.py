"""Parallel advisor token streams with first-token display order."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

StreamOne = Callable[[str], AsyncIterator[Dict[str, Any]]]
OnComplete = Callable[[str, Dict[str, Any]], Awaitable[None]]


async def iter_parallel_advisor_events(
    persona_ids: List[str],
    stream_one: StreamOne,
    timeout_seconds: float,
    persona_meta: Callable[[str], Dict[str, str]],
    on_complete: Optional[OnComplete] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Run advisor streams in parallel and yield NDJSON-ready event dicts.

    ``advisor_start`` is emitted on the first non-empty token for that persona
    so carousel order matches start-of-response, not rank or finish time.
    """
    queue: asyncio.Queue = asyncio.Queue()
    remaining = len(persona_ids)
    if remaining == 0:
        return

    async def _run(pid: str) -> None:
        meta = persona_meta(pid)
        started = False
        result: Optional[Dict[str, Any]] = None
        try:
            async def _consume() -> None:
                nonlocal started, result
                async for item in stream_one(pid):
                    if item.get("event") == "delta":
                        text = item.get("text") or ""
                        if not text:
                            continue
                        if not started:
                            started = True
                            await queue.put({
                                "type": "advisor_start",
                                "data": {
                                    "persona_id": pid,
                                    "persona_name": meta.get("persona_name", pid),
                                },
                            })
                        await queue.put({
                            "type": "advisor_delta",
                            "data": {
                                "persona_id": pid,
                                "delta": text,
                            },
                        })
                    elif item.get("event") == "done":
                        result = item.get("result") or {}

            await asyncio.wait_for(_consume(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "advisor stream %s timed out after %.1fs", pid, timeout_seconds,
            )
            result = {
                "persona_id": pid,
                "persona_name": meta.get("persona_name", pid),
                "response": (
                    "This advisor took too long to respond. "
                    "Please try again, or ask a more specific follow-up."
                ),
                "used_documents": False,
                "document_chunks_used": 0,
            }
        except Exception as e:
            logger.exception("advisor stream _run failed for %s: %s", pid, e)
            result = {
                "persona_id": pid,
                "persona_name": meta.get("persona_name", pid),
                "response": f"I ran into a technical issue. Please try again. ({e!s})",
                "used_documents": False,
                "document_chunks_used": 0,
            }

        if result is None:
            result = {
                "persona_id": pid,
                "persona_name": meta.get("persona_name", pid),
                "response": "",
                "used_documents": False,
                "document_chunks_used": 0,
            }

        if not started:
            await queue.put({
                "type": "advisor_start",
                "data": {
                    "persona_id": pid,
                    "persona_name": result.get("persona_name") or meta.get("persona_name", pid),
                },
            })

        if on_complete is not None:
            try:
                await on_complete(pid, result)
            except Exception as complete_err:
                logger.warning("advisor on_complete failed for %s: %s", pid, complete_err)

        await queue.put({
            "type": "advisor_done",
            "data": {
                "persona_id": result.get("persona_id", pid),
                "persona_name": result.get("persona_name") or meta.get("persona_name", pid),
                "content": result.get("response", ""),
                "used_documents": result.get("used_documents", False),
                "document_chunks_used": result.get("document_chunks_used", 0),
            },
        })

    tasks = [asyncio.create_task(_run(pid)) for pid in persona_ids]
    finished = 0
    first_start = True
    while finished < remaining:
        event = await queue.get()
        if first_start and event.get("type") == "advisor_start":
            first_start = False
            logger.info("first advisor token from %s", event.get("data", {}).get("persona_id"))
        yield event
        if event.get("type") == "advisor_done":
            finished += 1

    await asyncio.gather(*tasks, return_exceptions=True)
