from fastapi import APIRouter, Request, HTTPException
from app.core.session_manager import get_session_manager
from app.api.utils import get_or_create_session_for_request
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

session_manager = get_session_manager()

@router.get("/context")
async def get_context(request: Request):
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        rag_stats = session.get_rag_stats()
        return {
            "messages": session.messages,
            "rag_info": {
                "total_documents": rag_stats.get("total_documents", 0),
                "total_chunks": rag_stats.get("total_chunks", 0),
                "documents": rag_stats.get("documents", [])
            }
        }
    except Exception as e:
        logger.error(f"Error getting context: {str(e)}")
        return {"messages": [], "rag_info": {"total_documents": 0, "total_chunks": 0}}


@router.post("/reset-session")
async def reset_session(request: Request):
    try:
        session_id = get_or_create_session_for_request(request)
        success = session_manager.reset_session_completely(session_id)

        if success:
            return {"status": "reset", "message": "Session and all documents reset successfully"}
        else:
            return {"status": "error", "message": "Failed to reset session"}
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        return {"status": "error", "message": "Failed to reset session"}


@router.get("/session-stats")
async def get_session_stats(request: Request):
    try:
        session_id = get_or_create_session_for_request(request)
        stats = session_manager.get_session_stats(session_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting session stats: {str(e)}")
        return {"error": str(e)}
