"""Database connection facade.

Used to wrap pymongo / motor against a real MongoDB instance. For Hugging
Face Spaces deployment we now back the same public API with SQLite on a HF
Storage Bucket mount (see ``app.core.db``). The shim emulates the Mongo
idioms the routers and services use, so this module simply forwards to it
and keeps the legacy ``connect_to_mongo`` / ``close_mongo_connection`` /
``get_database`` API intact for ``main.py`` and the route files.
"""

import logging

from app.core.db import _close, _open, get_database as _get_database

logger = logging.getLogger(__name__)


async def connect_to_mongo() -> None:
    """Open the SQLite-backed database and run schema bootstrap."""
    await _open()
    logger.info("SQLite-backed database ready (Mongo API shim active).")
    # Legacy hook: previously called ``setup_canvas_collections`` here.
    # The phd_canvases table is already declared in the shim's schema, so
    # the call below is a no-op but kept for symmetry with the original
    # startup path.
    try:
        from app.core.canvas_database import setup_canvas_collections

        await setup_canvas_collections(_get_database())
        logger.info("Canvas database initialization completed (no-op on SQLite shim).")
    except Exception as canvas_error:  # pragma: no cover
        logger.error(f"Canvas database initialization failed: {canvas_error}")


async def close_mongo_connection() -> None:
    """Best-effort connection close on FastAPI shutdown."""
    await _close()
    logger.info("Disconnected from SQLite-backed database.")


async def create_indexes() -> None:
    """Index creation is handled by the shim's schema bootstrap; kept for
    backwards compatibility so any out-of-process maintenance script that
    imports this name keeps working."""
    return None


def get_database():
    """Return the SQLite-backed Mongo-API-compatible Database object."""
    return _get_database()
