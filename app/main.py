"""
Shortify Pro – Cloud URL Shortener with Analytics
Main application entry point.

Advanced modules:
  1. Redis Caching (hot short codes cached in Redis)
  2. Geo-Targeted Redirects (country-based URL routing)
  3. Password-Protected Links (password wall before redirect)
  4. Real-Time Analytics (WebSocket live click feed)
  5. Docker-ready (see docker-compose.yml)
"""

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import connect_db, close_db
from app.routes import auth, urls, analytics, admin
from app.services.url_service import get_url_by_short_code, increment_click, resolve_geo_target
from app.services.analytics_service import record_click, ws_manager, get_visitor_country
from app.models.schemas import UserRegister, UserLogin, URLCreate, TokenResponse, UserResponse, URLResponse, URLListResponse
from app.utils.security import get_current_user


# ─── Rate Limiter ───
limiter = Limiter(key_func=get_remote_address)


# ─── Lifespan ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


# ─── App ───
app = FastAPI(
    title="Shortify Pro",
    description="Cloud-Based URL Shortener with Analytics Dashboard – Redis Caching, Geo-Targeting, Password Protection, Real-Time WebSockets",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Show a nice HTML error page for 503 (database offline) on browser requests."""
    if exc.status_code == 503:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return templates.TemplateResponse(
                "503.html",
                {"request": request, "detail": exc.detail},
                status_code=503
            )
    # For all other HTTP errors (or API calls), return JSON
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(auth.router)
app.include_router(urls.router)
app.include_router(analytics.router)
app.include_router(admin.router)

# ─── Canonical API Aliases ───

@app.post("/register", response_model=TokenResponse, tags=["Canonical API"])
async def register_canonical(user_data: UserRegister):
    return await auth.register(user_data)

@app.post("/login", response_model=TokenResponse, tags=["Canonical API"])
async def login_canonical(user_data: UserLogin):
    return await auth.login(user_data)

@app.get("/profile", response_model=UserResponse, tags=["Canonical API"])
async def profile_canonical(user=Depends(get_current_user)):
    return await auth.get_profile(user)

@app.post("/shorten", response_model=URLResponse, tags=["Canonical API"])
async def shorten_canonical(url_data: URLCreate, request: Request, user=Depends(get_current_user)):
    return await urls.shorten_url(url_data, request, user)

@app.get("/links", response_model=URLListResponse, tags=["Canonical API"])
async def links_canonical(request: Request, skip: int = 0, limit: int = 50, tag: str = None, user=Depends(get_current_user)):
    return await urls.list_user_urls(request, skip, limit, tag, user)


# ─── Frontend Pages ───

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Serve the home page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/shortener", response_class=HTMLResponse)
async def shortener_page(request: Request):
    """Serve the dedicated URL shortener page."""
    return templates.TemplateResponse("shortener.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Serve the admin login page."""
    return templates.TemplateResponse("admin_login.html", {"request": request})



@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the register page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Serve the forgot password page."""
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    """Serve the reset password page."""
    return templates.TemplateResponse("reset_password.html", {"request": request})


@app.get("/url/settings/password/{short_code}", response_class=HTMLResponse)
async def config_password_page(short_code: str, request: Request):
    """Serve the page to configure URL password."""
    return templates.TemplateResponse("config_password.html", {"request": request, "short_code": short_code})


@app.get("/url/settings/geo/{short_code}", response_class=HTMLResponse)
async def config_geo_page(short_code: str, request: Request):
    """Serve the page to configure URL geo-targets."""
    return templates.TemplateResponse("config_geo.html", {"request": request, "short_code": short_code})


@app.get("/protected/{short_code}", response_class=HTMLResponse)
async def password_page(short_code: str, request: Request):
    """Serve the password entry page for protected links."""
    return templates.TemplateResponse("password.html", {"request": request, "short_code": short_code})

# ─── WebSocket Endpoints (Real-Time Analytics) ───

@app.websocket("/ws/analytics/{url_id}")
async def ws_url_analytics(websocket: WebSocket, url_id: str):
    """WebSocket for real-time click events on a specific URL."""
    await ws_manager.connect_url(websocket, url_id)
    try:
        while True:
            # Keep connection alive; client sends pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_url(websocket, url_id)


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """WebSocket for real-time click events across all user URLs."""
    await ws_manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_dashboard(websocket)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    """Serve the admin dashboard page."""
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})


# ─── Short URL Redirect (must be LAST) ───

@app.get("/{short_code}")
@limiter.limit("60/minute")
async def redirect_short_url(short_code: str, request: Request):
    """Redirect short URL to original URL with geo-targeting and password protection."""
    # Ignore common browser requests
    if short_code in ("favicon.ico", "robots.txt", "sitemap.xml"):
        return HTMLResponse(status_code=404)

    url_doc = await get_url_by_short_code(short_code)
    if not url_doc:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    # ─── Password Protection: redirect to password page ───
    if url_doc.get("password_hash"):
        return RedirectResponse(url=f"/protected/{short_code}", status_code=302)

    # ─── Geo-Targeting: resolve destination by visitor country ───
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")

    redirect_url = url_doc["original_url"]
    if url_doc.get("geo_targets"):
        country_code = await get_visitor_country(ip)
        redirect_url = resolve_geo_target(url_doc, country_code)

    # Record analytics
    await increment_click(url_doc["_id"])
    await record_click(url_doc["_id"], ip, ua)

    return RedirectResponse(url=redirect_url, status_code=302)
