"""URL routes: create, list, delete, verify password."""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import RedirectResponse
from app.models.schemas import URLCreate, URLResponse, URLListResponse, URLVerifyPassword, PasswordConfig, GeoConfig
from app.services.url_service import (
    create_short_url, get_url_by_short_code, increment_click,
    get_user_urls, delete_url, verify_url_password,
    update_url_password, update_url_geo, get_user_recent_count
)
from app.services.analytics_service import record_click
from app.utils.security import get_current_user, get_optional_user

router = APIRouter(tags=["URLs"])


@router.post("/api/shorten", response_model=URLResponse, status_code=status.HTTP_201_CREATED)
async def shorten_url(url_data: URLCreate, request: Request, user=Depends(get_current_user)):
    """Shorten a URL. Supports password protection and geo-targeting. (Rate Limited: 10/min)"""
    try:
        user_id = str(user["_id"]) if user else None
        
        # Rate Limiting: 10 links/min per user
        if user_id:
            recent_count = await get_user_recent_count(user_id, seconds=60)
            if recent_count >= 10:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded: You can only create 10 links per minute. Please wait."
                )

        # Build base URL from request so short URLs match the actual deployed domain
        base_url = str(request.base_url).rstrip("/")

        result = await create_short_url(
            original_url=url_data.original_url,
            user_id=user_id,
            custom_alias=url_data.custom_alias,
            expiry_days=url_data.expiry_days,
            password=url_data.password,
            geo_targets=url_data.geo_targets,
            tags=url_data.tags,
            base_url=base_url,
        )
        return URLResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/verify-password/{short_code}")
async def verify_link_password(short_code: str, body: URLVerifyPassword):
    """Verify password for a password-protected link. Returns the original URL."""
    url_doc = await get_url_by_short_code(short_code)
    if not url_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    if not url_doc.get("password_hash"):
        return {"original_url": url_doc["original_url"]}

    valid = await verify_url_password(short_code, body.password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong password")

    return {"original_url": url_doc["original_url"]}


@router.get("/api/user/urls", response_model=URLListResponse)
async def list_user_urls(request: Request, skip: int = 0, limit: int = 50, tag: str = None, user=Depends(get_current_user)):
    """Get all URLs for the current authenticated user. Supports filtering by tag."""
    base_url = str(request.base_url).rstrip("/")
    result = await get_user_urls(str(user["_id"]), skip=skip, limit=limit, tag=tag, base_url=base_url)
    return URLListResponse(**result)


@router.delete("/api/url/{url_id}", status_code=status.HTTP_200_OK)
async def remove_url(url_id: str, user=Depends(get_current_user)):
    """Delete a URL owned by the current user."""
    deleted = await delete_url(url_id, str(user["_id"]))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="URL not found or not owned by you"
        )
    return {"message": "URL deleted successfully"}


@router.put("/api/url/{short_code}/password", status_code=status.HTTP_200_OK)
async def update_password(short_code: str, config: PasswordConfig, user=Depends(get_current_user)):
    """Update or remove password protection for an existing URL."""
    success = await update_url_password(short_code, str(user["_id"]), config.password)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found or not owned by you")
    return {"message": "Password configuration updated successfully"}


@router.put("/api/url/{short_code}/geo", status_code=status.HTTP_200_OK)
async def update_geo(short_code: str, config: GeoConfig, user=Depends(get_current_user)):
    """Update or remove geo-targeting for an existing URL."""
    try:
        success = await update_url_geo(short_code, str(user["_id"]), config.geo_targets)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found or not owned by you")
        return {"message": "Geo-targeting configuration updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
