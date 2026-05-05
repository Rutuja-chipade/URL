"""Analytics service: tracking clicks, aggregation, WebSocket broadcasting, CSV export."""

from datetime import datetime, timezone
from bson import ObjectId
from app.database import get_db
from app.utils.helpers import parse_user_agent
import csv
import io
import asyncio
import json


# ─── WebSocket Connection Manager ───

class ConnectionManager:
    """Manages WebSocket connections for real-time analytics."""

    def __init__(self):
        # Maps url_id -> set of WebSocket connections
        self.active_connections: dict[str, set] = {}
        # Global dashboard connections (for live total stats)
        self.dashboard_connections: set = set()

    async def connect_url(self, websocket, url_id: str):
        await websocket.accept()
        if url_id not in self.active_connections:
            self.active_connections[url_id] = set()
        self.active_connections[url_id].add(websocket)

    async def connect_dashboard(self, websocket):
        await websocket.accept()
        self.dashboard_connections.add(websocket)

    def disconnect_url(self, websocket, url_id: str):
        if url_id in self.active_connections:
            self.active_connections[url_id].discard(websocket)
            if not self.active_connections[url_id]:
                del self.active_connections[url_id]

    def disconnect_dashboard(self, websocket):
        self.dashboard_connections.discard(websocket)

    async def broadcast_click(self, url_id: str, click_data: dict):
        """Broadcast a new click event to all listeners for this URL."""
        # Broadcast to URL-specific listeners
        if url_id in self.active_connections:
            dead = set()
            for ws in self.active_connections[url_id]:
                try:
                    await ws.send_json({
                        "type": "new_click",
                        "url_id": url_id,
                        "data": click_data,
                    })
                except Exception:
                    dead.add(ws)
            for ws in dead:
                self.active_connections[url_id].discard(ws)

        # Also broadcast to dashboard listeners
        dead = set()
        for ws in self.dashboard_connections:
            try:
                await ws.send_json({
                    "type": "new_click",
                    "url_id": url_id,
                    "data": click_data,
                })
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.dashboard_connections.discard(ws)


# Singleton manager
ws_manager = ConnectionManager()


async def record_click(url_id: ObjectId, ip_address: str, user_agent_str: str):
    """Record a click event and broadcast via WebSocket."""
    db = get_db()
    ua_info = parse_user_agent(user_agent_str)

    location_info = await _get_location_from_ip(ip_address)

    analytics_doc = {
        "url_id": url_id,
        "ip_address": ip_address,
        "location": location_info["display"],
        "country_code": location_info["country_code"],
        "device": ua_info["device"],
        "browser": ua_info["browser"],
        "os": ua_info["os"],
        "timestamp": datetime.now(timezone.utc),
    }

    await db.analytics.insert_one(analytics_doc)

    # Broadcast to WebSocket listeners (fire-and-forget)
    click_broadcast = {
        "location": location_info["display"],
        "device": ua_info["device"],
        "browser": ua_info["browser"],
        "os": ua_info["os"],
        "timestamp": analytics_doc["timestamp"].isoformat(),
    }
    asyncio.create_task(ws_manager.broadcast_click(str(url_id), click_broadcast))


async def get_visitor_country(ip_address: str) -> str:
    """Get the ISO country code for a visitor's IP for geo-targeting."""
    info = await _get_location_from_ip(ip_address)
    return info["country_code"]


async def get_analytics(url_id: str) -> dict:
    """Get aggregated analytics for a URL."""
    db = get_db()
    oid = ObjectId(url_id)

    url_doc = await db.urls.find_one({"_id": oid})
    if not url_doc:
        return None

    total_clicks = await db.analytics.count_documents({"url_id": oid})
    unique_ips = await db.analytics.distinct("ip_address", {"url_id": oid})
    unique_visitors = len(unique_ips)

    clicks_by_day = await _aggregate_by_field(oid, "day")
    clicks_by_browser = await _aggregate_group(oid, "$browser")
    clicks_by_device = await _aggregate_group(oid, "$device")
    clicks_by_location = await _aggregate_group(oid, "$location")

    recent = []
    cursor = db.analytics.find({"url_id": oid}).sort("timestamp", -1).limit(20)
    async for doc in cursor:
        recent.append({
            "ip_address": doc.get("ip_address", ""),
            "location": doc.get("location", "Unknown"),
            "device": doc.get("device", "Unknown"),
            "browser": doc.get("browser", "Unknown"),
            "os": doc.get("os", "Unknown"),
            "timestamp": doc["timestamp"].isoformat(),
        })

    return {
        "url_id": url_id,
        "original_url": url_doc["original_url"],
        "short_code": url_doc["short_code"],
        "total_clicks": total_clicks,
        "unique_visitors": unique_visitors,
        "clicks_by_day": clicks_by_day,
        "clicks_by_browser": clicks_by_browser,
        "clicks_by_device": clicks_by_device,
        "clicks_by_location": clicks_by_location,
        "recent_clicks": recent,
    }


async def export_analytics_csv(url_id: str) -> str:
    """Export analytics data as CSV string."""
    db = get_db()
    oid = ObjectId(url_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "IP Address", "Location", "Device", "Browser", "OS"])

    cursor = db.analytics.find({"url_id": oid}).sort("timestamp", -1)
    async for doc in cursor:
        writer.writerow([
            doc["timestamp"].isoformat(),
            doc.get("ip_address", ""),
            doc.get("location", "Unknown"),
            doc.get("device", "Unknown"),
            doc.get("browser", "Unknown"),
            doc.get("os", "Unknown"),
        ])

    return output.getvalue()


async def _aggregate_by_field(url_id: ObjectId, period: str) -> list:
    """Aggregate clicks by day."""
    db = get_db()
    pipeline = [
        {"$match": {"url_id": url_id}},
        {"$group": {
            "_id": {
                "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
        {"$limit": 30},
    ]
    results = []
    async for doc in db.analytics.aggregate(pipeline):
        results.append({"date": doc["_id"], "clicks": doc["count"]})
    return results


async def _aggregate_group(url_id: ObjectId, field: str) -> list:
    """Aggregate clicks by a specific field."""
    db = get_db()
    pipeline = [
        {"$match": {"url_id": url_id}},
        {"$group": {"_id": field, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    results = []
    async for doc in db.analytics.aggregate(pipeline):
        results.append({"label": doc["_id"] or "Unknown", "count": doc["count"]})
    return results


async def _get_location_from_ip(ip: str) -> dict:
    """Get location + country code from IP. Returns dict with display and country_code."""
    if ip in ("127.0.0.1", "localhost", "::1", "testclient"):
        return {"display": "Local", "country_code": ""}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip}?fields=city,country,countryCode")
            if resp.status_code == 200:
                data = resp.json()
                city = data.get("city", "")
                country = data.get("country", "")
                code = data.get("countryCode", "")
                display = f"{city}, {country}" if city and country else (country or "Unknown")
                return {"display": display, "country_code": code}
    except Exception:
        pass
    return {"display": "Unknown", "country_code": ""}
