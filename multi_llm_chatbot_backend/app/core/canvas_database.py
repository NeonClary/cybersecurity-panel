"""PhD Canvas database setup — SQLite-shim aware.

The original implementation was a Mongo-only module that created compound
indexes and a TTL index on the ``phd_canvases`` collection at startup. With
the SQLite-on-HF-bucket persistence shim, the schema (including the
``user_id`` index) is declared once at connection time inside
``app.core.db``, so this module becomes a compatibility no-op.

We keep the function signatures so any caller that still imports
``setup_canvas_collections`` or ``cleanup_old_canvas_data`` keeps working.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def setup_canvas_collections(db: Any) -> None:
    """No-op on the SQLite shim — indexes are created by ``app.core.db``."""
    logger.info(
        "PhD Canvas setup: schema and indexes are managed by the SQLite shim; "
        "skipping legacy Mongo index creation."
    )


async def cleanup_old_canvas_data(db: Any) -> None:
    """Maintenance helper — disabled on the SQLite shim.

    The original used a Mongo ``$lookup`` aggregation against the ``users``
    collection, which the in-process aggregation runner doesn't support. If
    you need the orphan cleanup, run it via a separate script that does two
    passes (``users``, then ``phd_canvases``) and calls ``delete_many``.
    """
    logger.info("cleanup_old_canvas_data is a no-op on the SQLite shim.")
