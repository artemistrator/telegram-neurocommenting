from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from backend.directus_client import directus
import logging
import traceback
import asyncio

router = APIRouter(prefix="/api", tags=["auth"])

logger = logging.getLogger(__name__)

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    email: str
    role: str

@router.post("/auth/login")
async def login(credentials: LoginRequest):
    """Login via Directus"""
    logger.info(f"Login attempt for: {credentials.email}")
    
    try:
        # Call Directus /auth/login
        response = await directus.client.post(
            "/auth/login",
            json={"email": credentials.email, "password": credentials.password}
        )
        
        logger.info(f"Directus response status: {response.status_code}")
        
        data = response.json()
        logger.info(f"Directus response data: {data}")
        
        if response.status_code != 200:
            logger.error(f"Directus login failed with status {response.status_code}: {data}")
            raise HTTPException(status_code=401, detail="Неверный email или пароль")
        
        if not data.get("data", {}).get("access_token"):
            logger.error("No access_token in Directus response")
            raise HTTPException(status_code=401, detail="Неверный email или пароль")
        
        return {
            "access_token": data.get("data", {}).get("access_token"),
            "refresh_token": data.get("data", {}).get("refresh_token"),
            "expires": data.get("data", {}).get("expires")
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=401, detail=f"Login error: {str(e)}")

@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current user - MOCK DATA"""
    
    logger.info("=== /auth/me called ===")
    
    token = request.cookies.get("access_token")
    logger.info(f"Token from cookie: {token[:30] if token else 'NONE'}...")
    
    if not token:
        logger.error("No token in cookie!")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # MOCK DATA - bypassing Directus for now
    mock_user = {
        "email": "ekaterina@test.com",
        "first_name": "Ekaterina",
        "last_name": "Muranova",
        "role": "Administrator"
    }
    
    logger.info(f"Returning mock user: {mock_user}")
    return mock_user


@router.post("/auth/logout")
async def logout():
    """Logout user"""
    # TODO: Invalidate token in Directus if needed
    return {"success": True}