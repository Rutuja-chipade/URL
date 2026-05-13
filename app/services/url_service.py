"""URL shortening service: CRUD operations, Redis caching, password protection, geo-targeting."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from bson import ObjectId
from app.database import get_db, cache_get, cache_set, cache_delete
from app.utils.helpers import generate_short_code, validate_url
from app.utils.security import hash_password, verify_password
from app.config import get_settings
import qrcode
import io
import base64

settings = get_settings()


async def create_short_url(
    original_url: str,
    user_id: Optional[str] = None,
    custom_alias: Optional[str] = None,
    expiry_days: Optional[int] = None,
    password: Optional[str] = None,
    geo_targets: Optional[dict[str, str]] = None,
    tags: Optional[list[str]] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Create a new shortened URL with optional password & geo-targeting."""
    db = get_db()

    if not validate_url(original_url):
        raise ValueError("Invalid URL format. Must start with http:// or https://")

    # Validate geo-target URLs
    if geo_targets:
        for country, target_url in geo_targets.items():
            if len(country) != 2:
                raise ValueError(f"Country code '{country}' must be a 2-letter ISO code")
            if not validate_url(target_url):
                raise ValueError(f"Invalid geo-target URL for {country}: {target_url}")

    # Use custom alias or generate short code
    if custom_alias:
        existing = await db.urls.find_one({"short_code": custom_alias})
        if existing:
            raise ValueError(f"Alias '{custom_alias}' is already taken")
        short_code = custom_alias
    else:
        short_code = generate_short_code()
        while await db.urls.find_one({"short_code": short_code}):
            short_code = generate_short_code()

    now = datetime.now(timezone.utc)
    expiry_date = None
    if expiry_days:
        expiry_date = now + timedelta(days=expiry_days)

    url_doc = {
        "original_url": original_url,
        "short_code": short_code,
        "user_id": ObjectId(user_id) if user_id else None,
        "created_at": now,
        "expiry_date": expiry_date,
        "total_clicks": 0,
        "password_hash": hash_password(password) if password else None,
        "geo_targets": geo_targets or {},
        "tags": tags or [],
    }

    result = await db.urls.insert_one(url_doc)
    url_doc["_id"] = result.inserted_id

    # Cache in Redis
    await _cache_url_doc(url_doc)

    return _format_url_response(url_doc, base_url=base_url)


async def get_url_by_short_code(short_code: str) -> Optional[dict]:
    """Fetch URL document by short code with Redis cache, checking expiry."""
    # Try Redis cache first
    cached = await cache_get(f"url:{short_code}")
    if cached:
        # Reconstruct ObjectId
        cached["_id"] = ObjectId(cached["_id"])
        if cached.get("user_id"):
            cached["user_id"] = ObjectId(cached["user_id"])
        # Parse dates back
        if cached.get("created_at"):
            cached["created_at"] = datetime.fromisoformat(cached["created_at"])
        if cached.get("expiry_date"):
            cached["expiry_date"] = datetime.fromisoformat(cached["expiry_date"])
            expiry = cached["expiry_date"]
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expiry:
                await cache_delete(f"url:{short_code}")
                return None
        return cached

    # Fallback to MongoDB
    db = get_db()
    url_doc = await db.urls.find_one({"short_code": short_code})

    if not url_doc:
        return None

    # Check expiry
    if url_doc.get("expiry_date"):
        expiry = url_doc["expiry_date"]
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry:
            return None

    # Store in cache for next time
    await _cache_url_doc(url_doc)

    return url_doc


async def verify_url_password(short_code: str, password: str) -> bool:
    """Verify the password for a password-protected URL."""
    url_doc = await get_url_by_short_code(short_code)
    if not url_doc or not url_doc.get("password_hash"):
        return False
    return verify_password(password, url_doc["password_hash"])


def resolve_geo_target(url_doc: dict, country_code: str) -> str:
    """Resolve the correct redirect URL based on visitor country."""
    geo_targets = url_doc.get("geo_targets", {})
    if country_code and geo_targets:
        # Try exact match first (e.g. "US"), then uppercase
        target = geo_targets.get(country_code) or geo_targets.get(country_code.upper())
        if target:
            return target
    return url_doc["original_url"]


async def increment_click(url_id: ObjectId):
    """Increment total clicks for a URL."""
    db = get_db()
    await db.urls.update_one(
        {"_id": url_id},
        {"$inc": {"total_clicks": 1}}
    )


async def get_user_recent_count(user_id: str, seconds: int = 60) -> int:
    """Count URLs created by a user in the last X seconds."""
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    count = await db.urls.count_documents({
        "user_id": ObjectId(user_id),
        "created_at": {"$gte": since}
    })
    return count


async def get_user_urls(user_id: str, skip: int = 0, limit: int = 50, tag: Optional[str] = None, base_url: Optional[str] = None) -> dict:
    """Get all URLs created by a user, optionally filtered by tag."""
    db = get_db()
    query = {"user_id": ObjectId(user_id)}
    if tag:
        query["tags"] = tag  # MongoDB filters arrays if the value is in them
        
    cursor = db.urls.find(query).sort("created_at", -1).skip(skip).limit(limit)
    urls = []
    async for doc in cursor:
        urls.append(_format_url_response(doc, base_url=base_url))

    total = await db.urls.count_documents(query)
    return {"urls": urls, "total": total}


async def delete_url(url_id: str, user_id: str) -> bool:
    """Delete a URL and its analytics, clear cache."""
    db = get_db()
    url_doc = await db.urls.find_one({"_id": ObjectId(url_id), "user_id": ObjectId(user_id)})
    if not url_doc:
        return False

    # Clear Redis cache
    await cache_delete(f"url:{url_doc['short_code']}")

    result = await db.urls.delete_one({"_id": ObjectId(url_id), "user_id": ObjectId(user_id)})
    if result.deleted_count > 0:
        await db.analytics.delete_many({"url_id": ObjectId(url_id)})
        return True
    return False

async def update_url_password(short_code: str, user_id: str, password: Optional[str]) -> bool:
    """Update or remove the password for a specific URL."""
    db = get_db()
    url_doc = await db.urls.find_one({"short_code": short_code, "user_id": ObjectId(user_id)})
    if not url_doc:
        return False
        
    password_hash = hash_password(password) if password else None
    
    await db.urls.update_one(
        {"_id": url_doc["_id"]},
        {"$set": {"password_hash": password_hash}}
    )
    
    url_doc["password_hash"] = password_hash
    await _cache_url_doc(url_doc)
    return True

async def update_url_geo(short_code: str, user_id: str, geo_targets: Optional[dict[str, str]]) -> bool:
    """Update or remove geo-targeting rules for a specific URL."""
    db = get_db()
    url_doc = await db.urls.find_one({"short_code": short_code, "user_id": ObjectId(user_id)})
    if not url_doc:
        return False
        
    geo_targets = geo_targets or {}
    
    # Validate
    for country, target_url in geo_targets.items():
        if len(country) != 2:
            raise ValueError(f"Country code '{country}' must be a 2-letter ISO code")
        if not validate_url(target_url):
            raise ValueError(f"Invalid geo-target URL for {country}: {target_url}")

    await db.urls.update_one(
        {"_id": url_doc["_id"]},
        {"$set": {"geo_targets": geo_targets}}
    )
    
    url_doc["geo_targets"] = geo_targets
    await _cache_url_doc(url_doc)
    return True


def generate_qr_code(short_url: str) -> str:
    """Generate a QR code as a base64 data URI."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(short_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#6c5ce7", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


async def _cache_url_doc(doc: dict):
    """Cache a URL document in Redis."""
    cache_data = {
        "_id": str(doc["_id"]),
        "original_url": doc["original_url"],
        "short_code": doc["short_code"],
        "user_id": str(doc["user_id"]) if doc.get("user_id") else None,
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "expiry_date": doc["expiry_date"].isoformat() if doc.get("expiry_date") else None,
        "total_clicks": doc.get("total_clicks", 0),
        "password_hash": doc.get("password_hash"),
        "geo_targets": doc.get("geo_targets", {}),
        "tags": doc.get("tags", []),
    }
    await cache_set(f"url:{doc['short_code']}", cache_data)


def _format_url_response(doc: dict, base_url: str = None) -> dict:
    """Format a URL mongo document into an API response."""
    base = base_url or settings.BASE_URL
    short_url = f"{base}/{doc['short_code']}"
    return {
        "id": str(doc["_id"]),
        "original_url": doc["original_url"],
        "short_code": doc["short_code"],
        "short_url": short_url,
        "created_at": doc["created_at"],
        "expiry_date": doc.get("expiry_date"),
        "total_clicks": doc.get("total_clicks", 0),
        "qr_code_url": generate_qr_code(short_url),
        "is_password_protected": bool(doc.get("password_hash")),
        "has_geo_targets": bool(doc.get("geo_targets")),
        "geo_targets": doc.get("geo_targets") or None,
        "tags": doc.get("tags", []),
    }
