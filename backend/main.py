import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional
import traceback
import json

from backend.routers import dashboard, proxies, accounts, templates, parser_router, tasks, channels, auth
from backend.directus_client import DirectusClient


# Pydantic models for subscriber
class ChannelListRequest(BaseModel):
    channel_urls: List[str]

class LimitsSettings(BaseModel):
    max_subs_per_day: int
    delay_min_seconds: int
    delay_max_seconds: int


# ============================================
# FASTAPI APP SETUP
# ============================================

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Directus client
directus_client = DirectusClient()


# ============================================
# STARTUP EVENT
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize Directus connection on startup"""
    print("Запуск приложения...")
    
    # Connect to Directus
    try:
        await directus_client.login()
        print("✓ Directus подключен")
    except Exception as e:
        print(f"⚠ Ошибка подключения к Directus: {e}")
    
    print("Приложение готово к работе")


# ============================================
# ROUTER REGISTRATION
# ============================================

app.include_router(dashboard.router)
app.include_router(proxies.router)
app.include_router(accounts.router)
app.include_router(templates.router)
app.include_router(parser_router.router)
app.include_router(tasks.router)
app.include_router(channels.router, prefix="/api/channels", tags=["channels"])
app.include_router(auth.router)


# ============================================
# FRONTEND SERVING
# ============================================

@app.get("/", response_class=HTMLResponse)
async def get_layout(request: Request):
    """Return layout with sidebar navigation"""
    # Redirect to login if not authenticated
    try:
        check_auth(request)
    except HTTPException:
        # If not authenticated, redirect to login page
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")
    
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Return login page"""
    with open("templates/login.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/pages/{page}", response_class=HTMLResponse)
async def get_page(page: str, request: Request):
    """Return individual page content"""
    # Redirect to login if not authenticated
    try:
        check_auth(request)
    except HTTPException:
        # If not authenticated, redirect to login page
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")
    
    try:
        page_path = os.path.join("pages", f"{page}.html")
        with open(page_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Page '{page}' not found")


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str, request: Request):
    """Catch-all route for SPA routing - returns layout.html for all non-API/static paths"""
    # Ignore API and static paths
    if full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("pages"):
        raise HTTPException(status_code=404)
    
    # Redirect to login if not authenticated (for protected pages)
    try:
        check_auth(request)
    except HTTPException:
        # If not authenticated, redirect to login page
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")
    
    # All other paths (home, accounts, subscriber, etc.) return layout
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


# ============================================
# SUBSCRIBER AND SETTINGS API ENDPOINTS (DEPRECATED)
# ============================================

@app.post("/api/subscriber/add-tasks", deprecated=True)
async def add_subscription_tasks(request: ChannelListRequest):
    """Add channels to subscription queue"""
    try:
        # Placeholder implementation - subscriber functionality is in backend/workers/subscription_worker.py
        return {
            "status": "success",
            "total_channels": len(request.channel_urls),
            "message": "This endpoint is deprecated. Use the subscription worker directly."
        }
    except Exception as e:
        print(f"Error adding subscription tasks: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/subscriber/stats", deprecated=True)
async def get_subscriber_stats():
    """Get subscription statistics"""
    try:
        # Placeholder implementation - subscriber functionality is in backend/workers/subscription_worker.py
        return {
            "pending": 0,
            "processing": 0,
            "done": 0,
            "errors": 0,
            "total": 0,
            "recent_tasks": [],
            "message": "This endpoint is deprecated. Use the subscription worker directly."
        }
    except Exception as e:
        print(f"Error getting subscriber stats: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings/limits", deprecated=True)
async def get_limits_settings():
    """Get current subscription limits"""
    try:
        # Placeholder implementation - settings functionality is in backend/workers/subscription_worker.py
        return {
            "max_subs_per_day": 20,
            "delay_min_seconds": 30,
            "delay_max_seconds": 120,
            "message": "This endpoint is deprecated. Use the subscription worker directly."
        }
    except Exception as e:
        print(f"Error getting limits: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/limits", deprecated=True)
async def update_limits_settings(settings: LimitsSettings):
    """Update subscription limits"""
    try:
        # Placeholder implementation - settings functionality is in backend/workers/subscription_worker.py
        return {
            "status": "success",
            "message": "This endpoint is deprecated. Use the subscription worker directly."
        }
    except Exception as e:
        print(f"Error updating limits: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# MAIN ENTRY POINT
# ============================================

def check_auth(request: Request):
    """Check if user has valid token"""
    # First check for token in Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        # In a real implementation, you would validate the token against Directus
        # For now, we'll just check if it exists
        return token
    
    # Also check for token in cookies (if we implement cookie storage later)
    token = request.cookies.get("access_token")
    if token:
        return token
    
    # If no token found, raise unauthorized exception
    raise HTTPException(status_code=401, detail="Unauthorized")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)