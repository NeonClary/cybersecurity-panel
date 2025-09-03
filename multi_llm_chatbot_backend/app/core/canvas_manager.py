import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

from app.models.phd_canvas import PhdCanvas, CanvasInsight, UpdateCanvasRequest
from app.core.canvas_analysis import CanvasAnalysisService
# Remove this import: from app.core.database import get_database
from app.core.bootstrap import llm

logger = logging.getLogger(__name__)

class CanvasManager:
    """Manages PhD Canvas creation, updates, and incremental processing"""
    
    def __init__(self):
        self.analysis_service = CanvasAnalysisService(llm_client=llm)
        self._db = None
    
    def get_database(self):
        """Lazy database connection to avoid circular imports"""
        if not self._db:
            # Import here to avoid circular import
            from app.core.database import get_database
            self._db = get_database()
        return self._db
    
    async def get_or_create_canvas(self, user_id: str) -> PhdCanvas:
        """Get existing canvas or create new one for user"""
        try:
            db = self.get_database()
            user_object_id = ObjectId(user_id)
            
            # Try to find existing canvas
            canvas_doc = await db.phd_canvases.find_one({"user_id": user_object_id})
            
            if canvas_doc:
                # Convert to PhdCanvas model
                canvas = PhdCanvas(**canvas_doc)
                logger.info(f"Found existing canvas for user {user_id} with {canvas.total_insights} insights")
                return canvas
            else:
                # Create new canvas
                canvas = PhdCanvas(user_id=user_object_id)
                
                # Insert into database
                result = await db.phd_canvases.insert_one(canvas.dict(by_alias=True))
                canvas.id = result.inserted_id
                
                logger.info(f"Created new canvas for user {user_id}")
                return canvas
                
        except Exception as e:
            logger.error(f"Error getting/creating canvas for user {user_id}: {e}")
            # Return empty canvas as fallback
            return PhdCanvas(user_id=ObjectId(user_id))
    
    async def update_canvas(self, user_id: str, request: UpdateCanvasRequest) -> PhdCanvas:
        """Update canvas with latest insights from chat sessions"""
        try:
            db = self.get_database()
            canvas = await self.get_or_create_canvas(user_id)
            
            logger.info(f"Updating canvas for user {user_id}, force_full={request.force_full_update}")
            
            # Determine which chats to process
            if request.force_full_update:
                # Process all chats
                chat_sessions = await self._get_all_user_chat_sessions(user_id)
                logger.info(f"Force full update: processing {len(chat_sessions)} total chat sessions")
            else:
                # Process only chats created/updated after last canvas update
                chat_sessions = await self._get_new_chat_sessions(user_id, canvas.last_chat_processed)
                logger.info(f"Incremental update: processing {len(chat_sessions)} new chat sessions since {canvas.last_chat_processed}")
            
            if not chat_sessions:
                logger.info("No new chat sessions to process")
                return canvas
            
            # Filter chat sessions if specific ones requested
            if request.include_chat_sessions:
                chat_sessions = [
                    chat for chat in chat_sessions 
                    if str(chat["_id"]) in request.include_chat_sessions
                ]
                logger.info(f"Filtered to {len(chat_sessions)} specifically requested chat sessions")
            
            # Process each chat session for insights
            all_new_insights = []
            processed_chat_ids = []
            
            for chat_session in chat_sessions:
                try:
                    chat_id = str(chat_session["_id"])
                    messages = chat_session.get("messages", [])
                    
                    if not messages:
                        continue
                    
                    logger.info(f"Processing chat {chat_id} with {len(messages)} messages")
                    
                    # Extract insights from this chat session
                    session_insights = await self.analysis_service.extract_insights_from_messages(
                        messages, chat_id
                    )
                    
                    if session_insights:
                        all_new_insights.extend(session_insights)
                        processed_chat_ids.append(chat_id)
                        logger.info(f"Extracted {len(session_insights)} insights from chat {chat_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing chat session {chat_session.get('_id')}: {e}")
                    continue
            
            if all_new_insights:
                # Categorize insights by section
                categorized_insights = self.analysis_service.categorize_insights(all_new_insights)
                
                # Update canvas sections
                sections_updated = 0
                for section_key, insights in categorized_insights.items():
                    if request.exclude_sections and section_key in request.exclude_sections:
                        continue
                    
                    # Prioritize insights before adding
                    prioritized_insights = self.analysis_service.prioritize_insights(insights)
                    
                    # Limit insights per section to avoid overwhelming canvas
                    max_insights_per_section = 10
                    limited_insights = prioritized_insights[:max_insights_per_section]
                    
                    if limited_insights:
                        canvas.update_section(section_key, limited_insights)
                        sections_updated += 1
                        logger.info(f"Updated section '{section_key}' with {len(limited_insights)} insights")
                
                # Update canvas metadata
                canvas.last_chat_processed = datetime.utcnow()
                canvas.last_updated = datetime.utcnow()
                
                # Save updated canvas to database
                await self._save_canvas(canvas)
                
                logger.info(f"Canvas update completed: {len(all_new_insights)} new insights, {sections_updated} sections updated")
            else:
                logger.info("No insights extracted from chat sessions")
            
            return canvas
            
        except Exception as e:
            logger.error(f"Error updating canvas for user {user_id}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    
    async def _get_all_user_chat_sessions(self, user_id: str) -> List[Dict]:
        """Get all chat sessions for a user"""
        try:
            db = self.get_database()
            user_object_id = ObjectId(user_id)
            
            cursor = db.chat_sessions.find({
                "user_id": user_object_id,
                "is_active": {"$ne": False},  # Include active sessions
                "deleted_at": {"$exists": False}  # Exclude deleted sessions
            }).sort("created_at", -1)  # Most recent first
            
            chat_sessions = await cursor.to_list(length=100)  # Limit to last 100 chats
            return chat_sessions
            
        except Exception as e:
            logger.error(f"Error getting all chat sessions for user {user_id}: {e}")
            return []
    
    async def _get_new_chat_sessions(self, user_id: str, since: Optional[datetime]) -> List[Dict]:
        """Get chat sessions created or updated after a specific time"""
        try:
            db = self.get_database()
            user_object_id = ObjectId(user_id)
            
            # Build query filter
            query_filter = {
                "user_id": user_object_id,
                "is_active": {"$ne": False},
                "deleted_at": {"$exists": False}
            }
            
            if since:
                # Get chats created or updated after the since timestamp
                query_filter["$or"] = [
                    {"created_at": {"$gt": since}},
                    {"updated_at": {"$gt": since}}
                ]
            else:
                # If no since time, get chats from last 7 days as default
                one_week_ago = datetime.utcnow() - timedelta(days=7)
                query_filter["created_at"] = {"$gte": one_week_ago}
            
            cursor = db.chat_sessions.find(query_filter).sort("created_at", -1)
            chat_sessions = await cursor.to_list(length=50)  # Limit for incremental updates
            
            return chat_sessions
            
        except Exception as e:
            logger.error(f"Error getting new chat sessions for user {user_id}: {e}")
            return []
    
    async def _save_canvas(self, canvas: PhdCanvas):
        """Save canvas to database"""
        try:
            db = self.get_database()
            
            # Update existing canvas
            await db.phd_canvases.replace_one(
                {"_id": canvas.id},
                canvas.dict(by_alias=True),
                upsert=True
            )
            
            logger.info(f"Saved canvas {canvas.id} to database")
            
        except Exception as e:
            logger.error(f"Error saving canvas to database: {e}")
            raise
    
    async def delete_canvas(self, user_id: str) -> bool:
        """Delete canvas for a user"""
        try:
            db = self.get_database()
            user_object_id = ObjectId(user_id)
            
            result = await db.phd_canvases.delete_one({"user_id": user_object_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted canvas for user {user_id}")
                return True
            else:
                logger.info(f"No canvas found to delete for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting canvas for user {user_id}: {e}")
            return False
    
    async def get_canvas_stats(self, user_id: str) -> Dict:
        """Get statistics about user's canvas"""
        try:
            canvas = await self.get_or_create_canvas(user_id)
            
            stats = {
                "total_insights": canvas.total_insights,
                "total_sections": len(canvas.sections),
                "last_updated": canvas.last_updated,
                "last_chat_processed": canvas.last_chat_processed,
                "created_at": canvas.created_at,
                "auto_update": canvas.auto_update,
                "sections_breakdown": {}
            }
            
            # Add breakdown by section
            for section_key, section in canvas.sections.items():
                stats["sections_breakdown"][section_key] = {
                    "title": section.title,
                    "insight_count": len(section.insights),
                    "last_updated": section.updated_at,
                    "priority": section.priority
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting canvas stats for user {user_id}: {e}")
            return {
                "total_insights": 0,
                "total_sections": 0,
                "error": str(e)
            }
    
    async def export_canvas_for_printing(self, user_id: str) -> Dict:
        """Export canvas in a print-optimized format"""
        try:
            canvas = await self.get_or_create_canvas(user_id)
            
            # Sort sections by priority and insight count
            sorted_sections = []
            for section_key, section in canvas.sections.items():
                if section.insights:  # Only include sections with insights
                    # Sort insights by confidence score
                    sorted_insights = sorted(
                        section.insights, 
                        key=lambda x: x.confidence_score, 
                        reverse=True
                    )
                    
                    sorted_sections.append({
                        "key": section_key,
                        "title": section.title,
                        "description": section.description,
                        "insights": [
                            {
                                "content": insight.content,
                                "source": insight.source_persona.title(),
                                "confidence": round(insight.confidence_score, 2)
                            }
                            for insight in sorted_insights[:8]  # Limit for printing
                        ],
                        "insight_count": len(section.insights),
                        "priority": section.priority
                    })
            
            # Sort sections by priority, then by insight count
            sorted_sections.sort(key=lambda x: (x["priority"], -x["insight_count"]))
            
            return {
                "user_id": user_id,
                "generated_at": datetime.utcnow(),
                "total_insights": canvas.total_insights,
                "last_updated": canvas.last_updated,
                "sections": sorted_sections,
                "metadata": {
                    "canvas_id": str(canvas.id),
                    "created_at": canvas.created_at,
                    "version": "1.0"
                }
            }
            
        except Exception as e:
            logger.error(f"Error exporting canvas for printing: {e}")
            raise

# Global canvas manager instance
canvas_manager = CanvasManager()

def get_canvas_manager() -> CanvasManager:
    """Get the global canvas manager instance"""
    return canvas_manager