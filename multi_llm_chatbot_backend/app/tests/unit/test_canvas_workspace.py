"""Unit tests for workspace / deliverables persistence on CanvasManager."""

import asyncio
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId


def _make_manager(user_id: str):
    with patch.dict(
        sys.modules,
        {
            "app.core.bootstrap": MagicMock(llm=MagicMock()),
            "app.core.canvas_analysis": MagicMock(
                CanvasAnalysisService=MagicMock(return_value=MagicMock())
            ),
        },
    ):
        sys.modules.pop("app.core.canvas_manager", None)
        from app.core.canvas_manager import CanvasManager

        mgr = CanvasManager()
        canvas_id = ObjectId()
        canvas_doc = {
            "_id": canvas_id,
            "user_id": ObjectId(user_id),
            "sections": {},
            "workspace": {},
            "deliverables": {},
            "created_at": datetime.utcnow(),
            "last_updated": datetime.utcnow(),
            "last_chat_processed": None,
            "total_insights": 0,
            "auto_update": True,
            "print_optimized": True,
        }

        db = SimpleNamespace()
        db.phd_canvases = MagicMock()
        db.phd_canvases.find_one = AsyncMock(return_value=canvas_doc)
        db.phd_canvases.replace_one = AsyncMock(return_value=MagicMock())
        db.phd_canvases.insert_one = AsyncMock(
            return_value=SimpleNamespace(inserted_id=canvas_id)
        )
        mgr.get_database = MagicMock(return_value=db)
        return mgr, db


def test_save_workspace_persists_layout_and_states():
    user_id = str(ObjectId())
    mgr, db = _make_manager(user_id)
    payload = {
        "layout": [{"id": "w-1", "type": "kanban", "size": "md"}],
        "states": {"kanban": {"columns": []}},
        "view": "workspace",
    }
    canvas = asyncio.run(mgr.save_workspace(user_id, payload))
    assert canvas.workspace["layout"][0]["type"] == "kanban"
    assert canvas.workspace["states"]["kanban"]["columns"] == []
    db.phd_canvases.replace_one.assert_awaited()


def test_save_deliverables_persists_projects():
    user_id = str(ObjectId())
    mgr, db = _make_manager(user_id)
    payload = {
        "activeProjectId": "p-abc",
        "projects": {
            "p-abc": {
                "id": "p-abc",
                "name": "IR Report",
                "templateId": "thesis-chapter",
                "sections": {"overview": "Hello"},
                "versions": [],
            }
        },
    }
    canvas = asyncio.run(mgr.save_deliverables(user_id, payload))
    assert canvas.deliverables["activeProjectId"] == "p-abc"
    assert canvas.deliverables["projects"]["p-abc"]["name"] == "IR Report"
    db.phd_canvases.replace_one.assert_awaited()
