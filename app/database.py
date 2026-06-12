"""MongoDB async database connection using Motor + Redis cache."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import HTTPException
from app.config import get_settings
import json
import certifi

settings = get_settings()

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None
redis_client = None


async def connect_db():
    """Create database connection and set up indexes."""
    global client, db, redis_client
    
    try:
        print(f"[LOG] Connecting to MongoDB: {settings.MONGO_URI.split('@')[-1] if '@' in settings.MONGO_URI else settings.MONGO_URI}")
        # Connect to actual MongoDB (from env or local)
        # Use certifi CA bundle to fix SSL/TLS issues on Windows
        client = AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=10000,  # Allow more time for Atlas
            connectTimeoutMS=10000,
            tlsCAFile=certifi.where(),
        )
        db = client[settings.DB_NAME]

        # Verify connection
        await client.admin.command('ping')

        # Create indexes for performance
        await db.urls.create_index("short_code", unique=True)
        await db.urls.create_index("user_id")
        await db.urls.create_index("created_at")
        await db.users.create_index("email", unique=True)
        await db.analytics.create_index("url_id")
        await db.analytics.create_index("timestamp")

        print(f"[OK] Connected to MongoDB: {settings.DB_NAME}")
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Could not connect to MongoDB: {error_msg}")
        if "TLSV1_ALERT_INTERNAL_ERROR" in error_msg or "SSL" in error_msg:
            print("[HINT] This is usually caused by your IP not being whitelisted in MongoDB Atlas.")
            print("[HINT] Go to MongoDB Atlas → Network Access → Add Current IP Address")
            print("[HINT] Or add 0.0.0.0/0 to allow all IPs (not recommended for production)")
        # We don't raise here so the app can start and listen on port, 
        # allowing Render to detect it's live and user to check logs.
        db = None

    # Connect to Redis (optional – degrades gracefully)
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await redis_client.ping()
        print("[OK] Connected to Redis cache")
    except Exception as e:
        redis_client = None
        print(f"[WARN] Redis not available (running without cache): {e}")


async def close_db():
    """Close database connection."""
    global client, redis_client
    if client:
        client.close()
        print("[LOG] MongoDB connection closed")
    if redis_client:
        await redis_client.close()
        print("[LOG] Redis connection closed")


def get_db() -> AsyncIOMotorDatabase:
    """Get database instance. Raises error if DB is not connected."""
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB Connection Error: The database is currently offline. If you are running locally, ensure MongoDB is started. If using MongoDB Atlas, make sure your current IP is whitelisted in Network Access settings. Go to MongoDB Atlas → Network Access → Add Current IP Address."
        )
    return db


def get_redis():
    """Get Redis client instance (may be None)."""
    return redis_client


# ─── Redis Cache Helpers ───

async def cache_set(key: str, value: dict, ttl: int = None):
    """Set a key in Redis cache with optional TTL."""
    r = get_redis()
    if not r:
        return
    try:
        ttl = ttl or settings.CACHE_TTL_SECONDS
        await r.setex(f"shortify:{key}", ttl, json.dumps(value, default=str))
    except Exception:
        pass


async def cache_get(key: str) -> dict | None:
    """Get a key from Redis cache."""
    r = get_redis()
    if not r:
        return None
    try:
        data = await r.get(f"shortify:{key}")
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


async def cache_delete(key: str):
    """Delete a key from Redis cache."""
    r = get_redis()
    if not r:
        return
    try:
        await r.delete(f"shortify:{key}")
    except Exception:
        pass
