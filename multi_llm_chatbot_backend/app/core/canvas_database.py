import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def setup_canvas_collections(db: AsyncIOMotorDatabase):
    """Setup MongoDB collections and indexes for PhD Canvas"""
    try:
        # Create indexes for phd_canvases collection
        canvas_indexes = [
            # User lookup index
            ("user_id", 1),
            # Query optimization indexes  
            [("user_id", 1), ("last_updated", -1)],
            [("user_id", 1), ("created_at", -1)],
            ("last_updated", -1),  # For cleanup operations
        ]
        
        collection = db.phd_canvases
        
        # Create indexes
        for index in canvas_indexes:
            if isinstance(index, list):
                # Compound index
                await collection.create_index(index)
                logger.info(f"Created compound index: {str(index)}")
            else:
                # Simple index
                await collection.create_index(index)
                logger.info(f"Created index: {str(index)}")
        
        # Ensure TTL index for old canvases (optional cleanup after 2 years)
        await collection.create_index(
            "created_at", 
            expireAfterSeconds=63072000  # 2 years in seconds
        )
        logger.info("Created TTL index for canvas cleanup")
        
        logger.info("PhD Canvas database setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error setting up canvas collections: {e}")
        raise

async def cleanup_old_canvas_data(db: AsyncIOMotorDatabase):
    """Cleanup old or orphaned canvas data (maintenance function)"""
    try:
        # Find canvases with no corresponding users (orphaned data)
        pipeline = [
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id", 
                    "foreignField": "_id",
                    "as": "user_data"
                }
            },
            {
                "$match": {
                    "user_data": {"$size": 0}  # No matching user found
                }
            }
        ]
        
        orphaned_canvases = await db.phd_canvases.aggregate(pipeline).to_list(length=100)
        
        if orphaned_canvases:
            orphaned_ids = [canvas["_id"] for canvas in orphaned_canvases]
            result = await db.phd_canvases.delete_many({"_id": {"$in": orphaned_ids}})
            logger.info(f"Cleaned up {result.deleted_count} orphaned canvas records")
        else:
            logger.info("No orphaned canvas records found")
            
    except Exception as e:
        logger.error(f"Error during canvas cleanup: {e}")