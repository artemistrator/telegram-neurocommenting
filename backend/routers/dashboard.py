"""
Dashboard analytics endpoint for retrieving system metrics and charts.
Provides comprehensive statistics, timeseries data, and recent activity.
"""

from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from backend.directus_client import directus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ============================================
# Pydantic Models
# ============================================

# Stats Models
class AccountStats(BaseModel):
    total: int
    active: int
    banned: int
    in_setup: int


class ProxyStats(BaseModel):
    total: int
    alive: int
    dead: int
    free: int


class QueueHealth(BaseModel):
    pending_tasks: int
    failed_tasks: int
    pending_subs: int
    pending_comments: int


class DashboardStats(BaseModel):
    accounts: AccountStats
    proxies: ProxyStats
    queue_health: QueueHealth


# Charts Models
class ChartDataPoint(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class DailyActivity(BaseModel):
    comments: List[ChartDataPoint]
    subscriptions: List[ChartDataPoint]
    posts_found: List[ChartDataPoint]


class SystemHealth(BaseModel):
    errors: List[ChartDataPoint]


class DashboardCharts(BaseModel):
    daily_activity: DailyActivity
    system_health: SystemHealth


# Recent Activity Models
class RecentComment(BaseModel):
    id: int
    text: str
    posted_at: str
    account_phone: str
    account_username: Optional[str]
    channel_title: str


class RecentSubscription(BaseModel):
    id: int
    subscribed_at: str
    channel_title: str
    channel_url: str


class RecentError(BaseModel):
    id: int
    level: str
    message: str
    created_at: str


class DashboardRecent(BaseModel):
    recent_comments: List[RecentComment]
    recent_subs: List[RecentSubscription]
    recent_errors: List[RecentError]


# ============================================
# Helper Functions
# ============================================

def fill_missing_dates(date_counts: Dict[str, int], start_date: datetime, days: int) -> List[ChartDataPoint]:
    """
    Fill missing dates with zero counts to ensure continuous timeseries.
    
    Args:
        date_counts: Dictionary mapping date strings to counts
        start_date: Start date for the range
        days: Number of days to fill
    
    Returns:
        List of ChartDataPoint with all dates filled
    """
    result = []
    current_date = start_date.date()
    
    for i in range(days):
        date_str = current_date.strftime('%Y-%m-%d')
        result.append(ChartDataPoint(
            date=date_str,
            count=date_counts.get(date_str, 0)
        ))
        current_date += timedelta(days=1)
    
    return result


# ============================================
# API Endpoints
# ============================================

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Get current dashboard statistics.
    
    Returns:
        - Account stats: total, active, banned, in_setup
        - Proxy stats: total, alive, dead, free
        - Queue health: pending/failed tasks, pending subs/comments
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        logger.info("Fetching dashboard stats...")
        
        # 1. Account Stats
        accounts_response = await directus.client.get("/items/accounts", params={
            "fields": "id,status,setup_status,user_created",
            "limit": -1
        })
        accounts_response.raise_for_status()
        accounts = accounts_response.json().get('data', [])
        
        account_stats = AccountStats(
            total=len(accounts),
            active=sum(1 for a in accounts if a.get('status') == 'active'),
            banned=sum(1 for a in accounts if a.get('status') == 'banned'),
            in_setup=sum(1 for a in accounts if a.get('setup_status') != 'completed')
        )
        
        # 2. Proxy Stats
        proxies_response = await directus.client.get("/items/proxies", params={
            "fields": "id,status,assigned_to,user_created",
            "limit": -1
        })
        proxies_response.raise_for_status()
        proxies = proxies_response.json().get('data', [])
        
        proxy_stats = ProxyStats(
            total=len(proxies),
            alive=sum(1 for p in proxies if p.get('status') in ['active', 'ok']),
            dead=sum(1 for p in proxies if p.get('status') in ['dead', 'failed']),
            free=sum(1 for p in proxies if not p.get('assigned_to'))
        )
        
        # 3. Queue Health
        # Task Queue - check if any records exist first
        tasks = []
        try:
            tasks_response = await directus.client.get("/items/task_queue", params={
                "fields": "id,status,user_created",
                "limit": -1
            })
            tasks_response.raise_for_status()
            tasks = tasks_response.json().get('data', [])
        except:
            logger.warning("Task queue collection may not exist or be accessible")
        
        # Subscription Queue
        subs = []
        try:
            subs_response = await directus.client.get("/items/subscription_queue", params={
                "fields": "id,status,user_created",
                "limit": -1
            })
            subs_response.raise_for_status()
            subs = subs_response.json().get('data', [])
        except:
            logger.warning("Subscription queue collection may not have accessible records")
        
        # Comment Queue
        comments = []
        try:
            comments_response = await directus.client.get("/items/comment_queue", params={
                "fields": "id,status,user_created",
                "limit": -1
            })
            comments_response.raise_for_status()
            comments = comments_response.json().get('data', [])
        except:
            logger.warning("Comment queue collection may not have accessible records")
        
        queue_health = QueueHealth(
            pending_tasks=sum(1 for t in tasks if t.get('status') in ['pending', 'processing']),
            failed_tasks=sum(1 for t in tasks if t.get('status') == 'failed'),
            pending_subs=sum(1 for s in subs if s.get('status') == 'pending'),
            pending_comments=sum(1 for c in comments if c.get('status') == 'pending')
        )
        
        logger.info(f"Stats: Accounts={account_stats.total}, Proxies={proxy_stats.total}")
        
        return DashboardStats(
            accounts=account_stats,
            proxies=proxy_stats,
            queue_health=queue_health
        )
        
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard stats: {str(e)}")


@router.get("/charts", response_model=DashboardCharts)
async def get_dashboard_charts(days: int = Query(30, ge=7, le=90)):
    """
    Get timeseries chart data for the specified number of days.
    
    Args:
        days: Number of days to include (7-90, default 30)
    
    Returns:
        - Daily activity: comments, subscriptions, posts_found
        - System health: errors
    
    Note: All missing dates are filled with zero counts.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        logger.info(f"Fetching chart data for {days} days...")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_iso = start_date.isoformat()
        
        # 1. Comments Activity (posted) - using correct field names from schema
        comments_by_date = {}
        try:
            comments_response = await directus.client.get("/items/comment_queue", params={
                "filter[status][_eq]": "posted",
                "filter[posted_at][_gte]": start_iso,  # Using 'posted_at' as found in schema
                "fields": "posted_at,user_created",
                "limit": -1
            })
            comments_response.raise_for_status()
            comments_data = comments_response.json().get('data', [])
            
            # Group by date
            for comment in comments_data:
                if comment.get('posted_at'):  # Using 'posted_at' as found in schema
                    try:
                        # Handle both with and without timezone
                        date_str = comment['posted_at'].replace('Z', '+00:00')  # Using 'posted_at' as found in schema
                        date_obj = datetime.fromisoformat(date_str).date()
                        date_key = date_obj.strftime('%Y-%m-%d')
                        comments_by_date[date_key] = comments_by_date.get(date_key, 0) + 1
                    except Exception as e:
                        logger.warning(f"Error parsing comment date: {e}")
        except Exception as e:
            logger.warning(f"Could not fetch comment queue data: {e}")
        
        # 2. Subscriptions Activity (subscribed) - using correct field names from schema
        subs_by_date = {}
        try:
            subs_response = await directus.client.get("/items/subscription_queue", params={
                "filter[status][_eq]": "subscribed",
                "filter[subscribed_at][_gte]": start_iso,  # Using 'subscribed_at' as found in schema
                "fields": "subscribed_at,user_created",  # Using 'subscribed_at' as found in schema
                "limit": -1
            })
            subs_response.raise_for_status()
            subs_data = subs_response.json().get('data', [])
            
            for sub in subs_data:
                if sub.get('subscribed_at'):  # Using 'subscribed_at' as found in schema
                    try:
                        date_str = sub['subscribed_at'].replace('Z', '+00:00')  # Using 'subscribed_at' as found in schema
                        date_obj = datetime.fromisoformat(date_str).date()
                        date_key = date_obj.strftime('%Y-%m-%d')
                        subs_by_date[date_key] = subs_by_date.get(date_key, 0) + 1
                    except Exception as e:
                        logger.warning(f"Error parsing subscription date: {e}")
        except Exception as e:
            logger.warning(f"Could not fetch subscription queue data: {e}")
        
        # 3. Posts Found Activity - using date_created as found in schema
        posts_by_date = {}
        try:
            posts_response = await directus.client.get("/items/found_posts", params={
                "filter[date_created][_gte]": start_iso,  # Using 'date_created' as found in schema
                "fields": "date_created,user_created",  # Using 'date_created' as found in schema
                "limit": -1
            })
            posts_response.raise_for_status()
            posts_data = posts_response.json().get('data', [])
            
            for post in posts_data:
                if post.get('date_created'):  # Using 'date_created' as found in schema
                    try:
                        date_str = post['date_created'].replace('Z', '+00:00')  # Using 'date_created' as found in schema
                        date_obj = datetime.fromisoformat(date_str).date()
                        date_key = date_obj.strftime('%Y-%m-%d')
                        posts_by_date[date_key] = posts_by_date.get(date_key, 0) + 1
                    except Exception as e:
                        logger.warning(f"Error parsing post date: {e}")
        except Exception as e:
            logger.warning(f"Could not fetch found posts data: {e}")
        
        # 4. System Health - Errors - using date_created as found in schema
        errors_by_date = {}
        try:
            errors_response = await directus.client.get("/items/task_events", params={
                "filter[level][_eq]": "error",
                "filter[date_created][_gte]": start_iso,  # Using 'date_created' as found in schema
                "fields": "date_created,user_created",  # Using 'date_created' as found in schema
                "limit": -1
            })
            errors_response.raise_for_status()
            errors_data = errors_response.json().get('data', [])
            
            for error in errors_data:
                if error.get('date_created'):  # Using 'date_created' as found in schema
                    try:
                        date_str = error['date_created'].replace('Z', '+00:00')  # Using 'date_created' as found in schema
                        date_obj = datetime.fromisoformat(date_str).date()
                        date_key = date_obj.strftime('%Y-%m-%d')
                        errors_by_date[date_key] = errors_by_date.get(date_key, 0) + 1
                    except Exception as e:
                        logger.warning(f"Error parsing error date: {e}")
        except Exception as e:
            logger.warning(f"Could not fetch task events data: {e}")
        
        # Fill missing dates for all series
        comments_filled = fill_missing_dates(comments_by_date, start_date, days)
        subs_filled = fill_missing_dates(subs_by_date, start_date, days)
        posts_filled = fill_missing_dates(posts_by_date, start_date, days)
        errors_filled = fill_missing_dates(errors_by_date, start_date, days)
        
        logger.info(f"Charts: {len(comments_by_date)} comments, {len(subs_by_date)} subs, {len(posts_by_date)} posts, {len(errors_by_date)} errors")
        
        return DashboardCharts(
            daily_activity=DailyActivity(
                comments=comments_filled,
                subscriptions=subs_filled,
                posts_found=posts_filled
            ),
            system_health=SystemHealth(
                errors=errors_filled
            )
        )
        
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch chart data: {str(e)}")


@router.get("/recent", response_model=DashboardRecent)
async def get_dashboard_recent():
    """
    Get recent activity: comments, subscriptions, and errors.
    
    Returns:
        - Recent 10 comments with account and channel info
        - Recent 10 subscriptions with channel info
        - Recent 10 errors/warnings
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        logger.info("Fetching recent activity...")
        
        # 1. Recent Comments (with JOINs) - using correct field names from schema
        recent_comments = []
        try:
            comments_response = await directus.client.get("/items/comment_queue", params={
                "filter[status][_eq]": "posted",
                "fields": "id,generated_comment,posted_at,account_id.phone,account_id.username,channel_url,user_created",  # Using 'posted_at' as found in schema
                "sort": "-posted_at",  # Using 'posted_at' as found in schema
                "limit": 3  # Only get 3 recent comments as requested
            })
            comments_response.raise_for_status()
            comments_data = comments_response.json().get('data', [])
            
            for c in comments_data:
                account_data = c.get('account_id', {}) or {}
                recent_comments.append(RecentComment(
                    id=c.get('id', 0),
                    text=(c.get('generated_comment') or 'N/A')[:100],  # Truncate to 100 chars
                    posted_at=c.get('posted_at', ''),  # Using 'posted_at' as found in schema
                    account_phone=account_data.get('phone', 'Unknown'),
                    account_username=account_data.get('username'),
                    channel_title=c.get('channel_url', 'Unknown')  # Using URL as title for now
                ))
        except Exception as e:
            logger.warning(f"Could not fetch comment queue data: {e}")
        
        # 2. Recent Subscriptions (with JOINs) - using correct field names from schema
        recent_subs = []
        try:
            subs_response = await directus.client.get("/items/subscription_queue", params={
                "filter[status][_eq]": "subscribed",
                "fields": "id,subscribed_at,found_channel_id.channel_title,found_channel_id.channel_url,user_created",  # Using 'subscribed_at' as found in schema
                "sort": "-subscribed_at",  # Using 'subscribed_at' as found in schema
                "limit": 3  # Only get 3 recent subscriptions
            })
            subs_response.raise_for_status()
            subs_data = subs_response.json().get('data', [])
            
            for s in subs_data:
                channel_data = s.get('found_channel_id', {}) or {}
                recent_subs.append(RecentSubscription(
                    id=s.get('id', 0),
                    subscribed_at=s.get('subscribed_at', ''),  # Using 'subscribed_at' as found in schema
                    channel_title=channel_data.get('channel_title', 'Unknown'),
                    channel_url=channel_data.get('channel_url', '')
                ))
        except Exception as e:
            logger.warning(f"Could not fetch subscription queue data: {e}")
        
        # 3. Recent Errors/Warnings - using correct field names from schema
        recent_errors = []
        try:
            errors_response = await directus.client.get("/items/task_events", params={
                "filter[level][_in]": "error,warning",
                "fields": "id,level,message,date_created,user_created",  # Using 'date_created' as found in schema
                "sort": "-date_created",  # Using 'date_created' as found in schema
                "limit": 3  # Only get 3 recent errors
            })
            errors_response.raise_for_status()
            errors_data = errors_response.json().get('data', [])
            
            for e in errors_data:
                recent_errors.append(RecentError(
                    id=e.get('id', 0),
                    level=e.get('level', 'unknown'),
                    message=(e.get('message') or 'No message')[:200],  # Truncate to 200 chars
                    created_at=e.get('date_created', '')  # Using 'date_created' as found in schema
                ))
        except Exception as e:
            logger.warning(f"Could not fetch task events data: {e}")
        
        logger.info(f"Recent: {len(recent_comments)} comments, {len(recent_subs)} subs, {len(recent_errors)} errors")
        
        return DashboardRecent(
            recent_comments=recent_comments,
            recent_subs=recent_subs,
            recent_errors=recent_errors
        )
        
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch recent activity: {str(e)}")