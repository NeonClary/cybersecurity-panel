import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def setup_canvas_collections(db: AsyncIOMotorDatabase):
    """Setup MongoDB collections and indexes for PhD Canvas"""
    try:
        collection = db.phd_canvases
        
        # Create simple indexes
        await collection.create_index("user_id")
        logger.info("Created index on user_id")
        
        await collection.create_index("last_updated", background=True)
        logger.info("Created index on last_updated")
        
        # Create compound indexes
        await collection.create_index([("user_id", 1), ("last_updated", -1)])
        logger.info("Created compound index on user_id and last_updated")
        
        await collection.create_index([("user_id", 1), ("created_at", -1)])
        logger.info("Created compound index on user_id and created_at")
        
        # Ensure TTL index for old canvases (optional cleanup after 2 years)
        await collection.create_index(
            "created_at", 
            expireAfterSeconds=63072000  # 2 years in seconds
        )
        logger.info("Created TTL index for canvas cleanup")
        
        logger.info("PhD Canvas database setup completed successfully")
        
    except Exception as e:
        logger.error("Error setting up canvas collections: %s", str(e))
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
            logger.info("Cleaned up %d orphaned canvas records", result.deleted_count)
        else:
            logger.info("No orphaned canvas records found")
            
    except Exception as e:
        logger.error("Error during canvas cleanup: %s", str(e))