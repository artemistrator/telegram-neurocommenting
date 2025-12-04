"""
Dashboard statistics endpoint for retrieving system metrics.
Provides account and proxy statistics with user isolation.
"""

from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import logging

from backend.directus_client import directus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# Response models
class AccountStats(BaseModel):
    active: int
    banned: int
    reserve: int
    total: int


class ProxyStats(BaseModel):
    active: int
    dead: int


class DashboardStatsResponse(BaseModel):
    accounts: AccountStats
    proxies: ProxyStats
    system_health: str


async def get_current_user_id() -> Optional[str]:
    """
    Get current user ID from Directus authentication.
    In a real implementation, this would extract user_id from JWT token.
    For now, we'll use a placeholder approach.
    
    TODO: Implement proper JWT token parsing to extract user_created UUID
    """
    # This is a placeholder - in production, you would:
    # 1. Extract JWT token from Authorization header
    # 2. Decode the token to get user ID
    # 3. Return the user_created UUID
    
    # For now, return None to fetch all data (admin mode)
    # In production, replace this with actual user ID extraction
    return None


async def get_account_stats(user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Fetch account statistics from Directus.
    
    Args:
        user_id: Optional user UUID for filtering. If None, fetches all accounts.
    
    Returns:
        Dict with counts for each status: active, banned, reserve
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Base filter params
        base_params = {
            "fields": "id,status",
            "limit": -1  # Get all records
        }
        
        # Add user filter if user_id is provided
        if user_id:
            base_params["filter[user_created][_eq]"] = user_id
        
        # Fetch all accounts
        response = await directus.client.get("/items/accounts", params=base_params)
        response.raise_for_status()
        
        accounts = response.json().get('data', [])
        
        # Count by status
        stats = {
            'active': 0,
            'banned': 0,
            'reserve': 0,
            'total': len(accounts)
        }
        
        for account in accounts:
            status = account.get('status', '').lower()
            if status in stats:
                stats[status] += 1
        
        logger.info(f"Account stats for user {user_id or 'all'}: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching account stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch account stats: {str(e)}")


async def get_proxy_stats(user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Fetch proxy statistics from Directus.
    
    Args:
        user_id: Optional user UUID for filtering. If None, fetches all proxies.
    
    Returns:
        Dict with counts for each status: active, dead
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Base filter params
        base_params = {
            "fields": "id,status",
            "limit": -1  # Get all records
        }
        
        # Add user filter if user_id is provided
        if user_id:
            base_params["filter[user_created][_eq]"] = user_id
        
        # Fetch all proxies
        response = await directus.client.get("/items/proxies", params=base_params)
        response.raise_for_status()
        
        proxies = response.json().get('data', [])
        
        # Count by status
        stats = {
            'active': 0,
            'dead': 0
        }
        
        for proxy in proxies:
            status = proxy.get('status', '').lower()
            if status == 'active' or status == 'ok':
                stats['active'] += 1
            elif status == 'dead' or status == 'failed':
                stats['dead'] += 1
        
        logger.info(f"Proxy stats for user {user_id or 'all'}: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching proxy stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch proxy stats: {str(e)}")


def calculate_system_health(account_stats: Dict[str, int]) -> str:
    """
    Calculate system health based on reserve account availability.
    
    Logic:
    - "ok" if reserve accounts >= 3
    - "warning" if reserve accounts < 3
    
    Args:
        account_stats: Dictionary with account statistics
    
    Returns:
        Health status: "ok" or "warning"
    """
    reserve_count = account_stats.get('reserve', 0)
    
    if reserve_count >= 3:
        return "ok"
    else:
        return "warning"


# API Endpoints

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats():
    """
    Get dashboard statistics for the current user.
    
    Returns:
        - Account statistics (active, banned, reserve, total)
        - Proxy statistics (active, dead)
        - System health status
    
    Note: Currently returns all data (admin mode).
    TODO: Implement user authentication to filter by user_created.
    """
    try:
        # Get current user ID (placeholder - returns None for now)
        user_id = await get_current_user_id()
        
        # Fetch statistics
        account_stats = await get_account_stats(user_id)
        proxy_stats = await get_proxy_stats(user_id)
        
        # Calculate system health
        system_health = calculate_system_health(account_stats)
        
        # Build response
        response = {
            "accounts": {
                "active": account_stats['active'],
                "banned": account_stats['banned'],
                "reserve": account_stats['reserve'],
                "total": account_stats['total']
            },
            "proxies": {
                "active": proxy_stats['active'],
                "dead": proxy_stats['dead']
            },
            "system_health": system_health
        }
        
        logger.info(f"Dashboard stats retrieved for user {user_id or 'all'}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")
