"""Admin API routes for managing users and URLs."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.utils.security import get_current_admin
from app.services.url_service import delete_url

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(get_current_admin)])

# ─── Schemas for Admin Responses ───

class AdminStatsResponse(BaseModel):
    total_users: int
    total_urls: int
    total_clicks: int

class AdminUserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    is_admin: bool
    role: str

# ─── Admin Routes ───

@router.get("/stats", response_model=AdminStatsResponse)
async def get_system_stats():
    """Get overall system statistics."""
    db = get_db()
    total_users = await db.users.count_documents({})
    total_urls = await db.urls.count_documents({})
    
    # Sum up all clicks
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$total_clicks"}}}]
    result = await db.urls.aggregate(pipeline).to_list(1)
    
    total_clicks = result[0]["total"] if result else 0

    return {
        "total_users": total_users,
        "total_urls": total_urls,
        "total_clicks": total_clicks
    }


@router.get("/users", response_model=List[AdminUserResponse])
async def list_all_users(skip: int = 0, limit: int = 100):
    """List all registered users in the system."""
    db = get_db()
    cursor = db.users.find({}).sort("created_at", -1).skip(skip).limit(limit)
    users = []
    async for doc in cursor:
        users.append({
            "id": str(doc["_id"]),
            "name": doc["name"],
            "email": doc["email"],
            "created_at": doc["created_at"],
            "is_admin": doc.get("is_admin", False),
            "role": doc.get("role", "admin" if doc.get("is_admin") else "user")
        })
    return users


@router.delete("/user/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user_and_data(user_id: str):
    """Hard delete a user and all of their URLs/analytics."""
    db = get_db()
    try:
        oid = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid User ID")

    # Verify user exists
    user = await db.users.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Prevent deleting other admins to avoid locking out the system unintentionally
    if user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Cannot delete an admin user directly")

    # Find all user URLs to delete their analytics
    user_urls = db.urls.find({"user_id": oid})
    url_ids = [doc["_id"] async for doc in user_urls]

    if url_ids:
        # Delete all analytics for these URLs
        await db.analytics.delete_many({"url_id": {"$in": url_ids}})
        # Delete all URLs
        await db.urls.delete_many({"user_id": oid})

    # Finally, delete the user
    await db.users.delete_one({"_id": oid})

    return {"message": "User and all associated data deleted successfully."}


@router.get("/urls")
async def list_all_urls(request: Request, skip: int = 0, limit: int = 50):
    """List all URLs across all users."""
    db = get_db()
    cursor = db.urls.find({}).sort("created_at", -1).skip(skip).limit(limit)
    urls = []
    
    from app.services.url_service import _format_url_response
    base_url = str(request.base_url).rstrip("/")
    
    async for doc in cursor:
        formatted = _format_url_response(doc, base_url=base_url)
        formatted["user_id"] = str(doc["user_id"]) if doc.get("user_id") else None
        urls.append(formatted)
        
    total = await db.urls.count_documents({})
    return {"urls": urls, "total": total}


@router.delete("/url/{url_id}", status_code=status.HTTP_200_OK)
async def admin_delete_url(url_id: str):
    """Delete any URL as an admin."""
    from app.database import cache_delete
    db = get_db()
    try:
        oid = ObjectId(url_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid URL ID")

    url_doc = await db.urls.find_one({"_id": oid})
    if not url_doc:
        raise HTTPException(status_code=404, detail="URL not found")

    # Clear cache
    await cache_delete(f"url:{url_doc['short_code']}")

    # Delete analytics and URL
    await db.analytics.delete_many({"url_id": oid})
    await db.urls.delete_one({"_id": oid})

    return {"message": "URL deleted successfully"}


@router.post("/urls/bulk-upload")
async def bulk_upload_urls(request: Request, file: UploadFile = File(...), user = Depends(get_current_admin)):
    """Bulk upload URLs using a CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = await file.read()
    try:
        decoded = content.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")
        
    import csv
    import io
    reader = csv.DictReader(io.StringIO(decoded))
    if "url" not in (reader.fieldnames or []):
        raise HTTPException(status_code=400, detail="CSV must contain a 'url' column")
        
    results = []
    db = get_db()
    
    from app.services.url_service import create_short_url
    base_url = str(request.base_url).rstrip("/")
    
    for row in reader:
        original_url = row.get("url", "").strip()
        if not original_url:
            continue
            
        existing = await db.urls.find_one({"original_url": original_url, "user_id": ObjectId(user["_id"])})
        if existing:
            results.append({
                "original_url": original_url,
                "short_url": f"{base_url}/{existing['short_code']}",
                "status": "skipped",
                "message": "Already generated by you"
            })
            continue
            
        try:
            url_res = await create_short_url(original_url=original_url, user_id=str(user["_id"]), base_url=base_url)
            results.append({
                "original_url": original_url,
                "short_url": url_res["short_url"],
                "status": "success",
                "message": "Created"
            })
        except ValueError as e:
            results.append({
                "original_url": original_url,
                "short_url": "-",
                "status": "error",
                "message": str(e)
            })
        except Exception as e:
            results.append({
                "original_url": original_url,
                "short_url": "-",
                "status": "error",
                "message": "Internal error"
            })
            
    return {"results": results}
