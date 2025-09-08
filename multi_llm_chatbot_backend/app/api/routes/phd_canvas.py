from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import Dict, Optional
from datetime import datetime
import logging

from app.models.user import User
from app.models.phd_canvas import PhdCanvas, CanvasResponse, UpdateCanvasRequest
from app.core.auth import get_current_active_user

from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class CanvasStatsResponse(BaseModel):
    total_insights: int
    total_sections: int
    last_updated: Optional[str] = None
    last_chat_processed: Optional[str] = None
    created_at: Optional[str] = None
    auto_update: bool = True
    sections_breakdown: Dict = {}

class PrintCanvasResponse(BaseModel):
    user_id: str
    generated_at: str
    total_insights: int
    last_updated: Optional[str] = None
    sections: list
    metadata: Dict

def get_canvas_manager():
    """Lazy import to avoid circular dependency"""
    from app.core.canvas_manager import get_canvas_manager
    return get_canvas_manager()

@router.get("/phd-canvas", response_model=CanvasResponse)
async def get_phd_canvas(
    current_user: User = Depends(get_current_active_user)
):
    """Get the user's PhD Canvas, creating it if it doesn't exist"""
    try:
        canvas_manager = get_canvas_manager()
        canvas = await canvas_manager.get_or_create_canvas(str(current_user.id))
        
        # Convert to response model
        return CanvasResponse(
            id=str(canvas.id),
            user_id=str(canvas.user_id),
            sections=canvas.sections,
            created_at=canvas.created_at,
            last_updated=canvas.last_updated,
            last_chat_processed=canvas.last_chat_processed,
            total_insights=canvas.total_insights,
            auto_update=canvas.auto_update,
            print_optimized=canvas.print_optimized
        )
        
    except Exception as e:
        logger.error(f"Error getting PhD canvas for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve PhD canvas"
        )

@router.post("/phd-canvas/update", response_model=CanvasResponse)
async def update_phd_canvas(
    request: UpdateCanvasRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """Update the PhD Canvas with latest insights from chat sessions"""
    try:
        canvas_manager = get_canvas_manager()
        
        # For large updates, run in background
        if request.force_full_update:
            logger.info(f"Queuing background canvas update for user {current_user.id}")
            background_tasks.add_task(
                _background_canvas_update,
                str(current_user.id),
                request
            )
            
            # Return current canvas immediately
            canvas = await canvas_manager.get_or_create_canvas(str(current_user.id))
        else:
            # For incremental updates, process immediately
            logger.info(f"Processing incremental canvas update for user {current_user.id}")
            canvas = await canvas_manager.update_canvas(str(current_user.id), request)
        
        return CanvasResponse(
            id=str(canvas.id),
            user_id=str(canvas.user_id),
            sections=canvas.sections,
            created_at=canvas.created_at,
            last_updated=canvas.last_updated,
            last_chat_processed=canvas.last_chat_processed,
            total_insights=canvas.total_insights,
            auto_update=canvas.auto_update,
            print_optimized=canvas.print_optimized
        )
        
    except Exception as e:
        logger.error(f"Error updating PhD canvas for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update PhD canvas"
        )

@router.get("/phd-canvas/stats", response_model=CanvasStatsResponse)
async def get_canvas_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get statistics about the user's PhD Canvas"""
    try:
        canvas_manager = get_canvas_manager()
        stats = await canvas_manager.get_canvas_stats(str(current_user.id))
        
        return CanvasStatsResponse(
            total_insights=stats.get("total_insights", 0),
            total_sections=stats.get("total_sections", 0),
            last_updated=stats.get("last_updated").isoformat() if stats.get("last_updated") else None,
            last_chat_processed=stats.get("last_chat_processed").isoformat() if stats.get("last_chat_processed") else None,
            created_at=stats.get("created_at").isoformat() if stats.get("created_at") else None,
            auto_update=stats.get("auto_update", True),
            sections_breakdown=stats.get("sections_breakdown", {})
        )
        
    except Exception as e:
        logger.error(f"Error getting canvas stats for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve canvas statistics"
        )

@router.get("/phd-canvas/print", response_model=PrintCanvasResponse)
async def get_print_canvas(
    current_user: User = Depends(get_current_active_user)
):
    """Get PhD Canvas formatted for printing"""
    try:
        canvas_manager = get_canvas_manager()
        print_data = await canvas_manager.export_canvas_for_printing(str(current_user.id))
        
        return PrintCanvasResponse(
            user_id=print_data["user_id"],
            generated_at=print_data["generated_at"].isoformat(),
            total_insights=print_data["total_insights"],
            last_updated=print_data["last_updated"].isoformat() if print_data["last_updated"] else None,
            sections=print_data["sections"],
            metadata=print_data["metadata"]
        )
        
    except Exception as e:
        logger.error(f"Error exporting print canvas for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export canvas for printing"
        )

@router.post("/phd-canvas/auto-update")
async def trigger_auto_update(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """Trigger automatic canvas update (typically called when user opens canvas page)"""
    try:
        canvas_manager = get_canvas_manager()
        
        # Get current canvas to check if auto-update is needed
        canvas = await canvas_manager.get_or_create_canvas(str(current_user.id))
        
        if not canvas.auto_update:
            return {"message": "Auto-update is disabled for this canvas"}
        
        # Check if this is a first-time canvas (never processed any chats)
        is_first_time_canvas = (
            canvas.last_chat_processed is None and 
            canvas.total_insights == 0
        )
        
        # Check if we need to update (has been more than 1 hour since last update)
        from datetime import timedelta
        needs_regular_update = (
            canvas.last_updated is None or 
            (datetime.utcnow() - canvas.last_updated) > timedelta(hours=1)
        )
        
        if is_first_time_canvas:
            logger.info(f"First-time canvas detected for user {current_user.id}, triggering full update")
            
            # For first-time canvas, always do full update to process all historical chats
            background_tasks.add_task(
                _background_canvas_update,
                str(current_user.id),
                UpdateCanvasRequest(force_full_update=True)
            )
            
            return {
                "message": "First-time canvas update initiated", 
                "status": "processing",
                "type": "full_update"
            }
            
        elif needs_regular_update:
            logger.info(f"Regular auto-updating canvas for user {current_user.id}")
            
            # For existing canvas, do incremental update
            background_tasks.add_task(
                _background_canvas_update,
                str(current_user.id),
                UpdateCanvasRequest(force_full_update=False)
            )
            
            return {
                "message": "Canvas update queued", 
                "status": "updating",
                "type": "incremental_update"
            }
        else:
            return {
                "message": "Canvas is up to date", 
                "status": "current"
            }
            
    except Exception as e:
        logger.error(f"Error triggering auto-update for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger canvas auto-update"
        )

@router.delete("/phd-canvas")
async def delete_canvas(
    current_user: User = Depends(get_current_active_user)
):
    """Delete the user's PhD Canvas"""
    try:
        canvas_manager = get_canvas_manager()
        deleted = await canvas_manager.delete_canvas(str(current_user.id))
        
        if deleted:
            return {"message": "PhD Canvas deleted successfully"}
        else:
            return {"message": "No canvas found to delete"}
            
    except Exception as e:
        logger.error(f"Error deleting canvas for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete PhD canvas"
        )

@router.get("/phd-canvas/refresh")
async def refresh_canvas_data(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """Force refresh canvas with full update from all chats"""
    try:
        logger.info(f"Force refreshing canvas for user {current_user.id}")
        
        # Queue full update in background
        background_tasks.add_task(
            _background_canvas_update,
            str(current_user.id),
            UpdateCanvasRequest(force_full_update=True)
        )
        
        return {
            "message": "Full canvas refresh initiated",
            "status": "processing",
            "estimated_completion": "2-3 minutes"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing canvas for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh PhD canvas"
        )

# Background task functions
async def _background_canvas_update(user_id: str, request: UpdateCanvasRequest):
    """Background task to update canvas without blocking the API response"""
    try:
        logger.info(f"Starting background canvas update for user {user_id}")
        canvas_manager = get_canvas_manager()
        
        updated_canvas = await canvas_manager.update_canvas(user_id, request)
        
        logger.info(f"Background canvas update completed for user {user_id}. Total insights: {updated_canvas.total_insights}")
        
    except Exception as e:
        logger.error(f"Error in background canvas update for user {user_id}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

# Health check endpoint
@router.get("/phd-canvas/health")
async def canvas_health_check():
    """Health check for canvas service"""
    try:
        canvas_manager = get_canvas_manager()
        return {
            "status": "healthy",
            "service": "phd-canvas",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Canvas health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canvas service is not healthy"
        )