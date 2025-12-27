import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException

from backend.routers import dashboard, proxies, accounts, templates, parser_router, tasks, channels
from backend.directus_client import DirectusClient


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


# ============================================
# FRONTEND SERVING
# ============================================

@app.get("/", response_class=HTMLResponse)
async def get_layout():
    """Return layout with sidebar navigation"""
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/pages/{page}", response_class=HTMLResponse)
async def get_page(page: str):
    """Return individual page content"""
    try:
        page_path = os.path.join("pages", f"{page}.html")
        with open(page_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Page '{page}' not found")


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    """Catch-all route for SPA routing - returns layout.html for all non-API/static paths"""
    # Ignore API and static paths
    if full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("pages"):
        raise HTTPException(status_code=404)
    
    # All other paths (home, accounts, subscriber, etc.) return layout
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)