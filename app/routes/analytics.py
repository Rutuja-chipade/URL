"""Analytics routes: get analytics, export CSV."""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from app.services.analytics_service import get_analytics, export_analytics_csv
from app.utils.security import get_current_user
from app.database import get_db
from bson import ObjectId
import io

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/{url_id}")
async def get_url_analytics(url_id: str, user=Depends(get_current_user)):
    """Get analytics for a specific URL."""
    # Verify ownership
    db = get_db()
    url_doc = await db.urls.find_one({"_id": ObjectId(url_id)})
    if not url_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")

    if url_doc.get("user_id") and str(url_doc["user_id"]) != str(user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    analytics = await get_analytics(url_id)
    if not analytics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analytics not found")
    return analytics


@router.get("/{url_id}/csv")
async def download_csv(url_id: str, user=Depends(get_current_user)):
    """Download analytics as CSV file."""
    db = get_db()
    url_doc = await db.urls.find_one({"_id": ObjectId(url_id)})
    if not url_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")

    if url_doc.get("user_id") and str(url_doc["user_id"]) != str(user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    csv_data = await export_analytics_csv(url_id)

    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=analytics_{url_doc['short_code']}.csv"}
    )
