from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime

from backend.directus_client import DirectusClient
import logging

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parser", tags=["parser"])
directus = DirectusClient()

# Pydantic models
class StartSearchRequest(BaseModel):
    keywords: List[str]
    min_subscribers: int = 100

class AddToMonitoringRequest(BaseModel):
    channel_ids: List[int]

# Endpoints
@router.post("/start-search")
async def start_search(data: StartSearchRequest):
    """
    Start search process for given keywords.
    Creates 'active' search_keywords entries with frequency 'once'.
    """
    try:
        created_count = 0
        
        for keyword in data.keywords:
            keyword = keyword.strip()
            if not keyword:
                continue
                
            # Prepare data for new keyword
            keyword_data = {
                "keyword": keyword,
                "status": "active",
                "search_frequency": "once",
                "min_subscribers": data.min_subscribers,
                "last_search_at": None,  # Will be set by worker when search starts
                "channels_found": 0
            }
            
            # Create in Directus using DirectusClient
            # We don't need to check for duplicates here as Directus usually handles uniques if configured, 
            # or we just create a new search task. 
            # If we want to avoid duplicates, we could search first.
            # For this task, simple creation is requested.
            
            await directus.create_item("search_keywords", keyword_data)
            created_count += 1
            
        return {"status": "success", "count": created_count}
        
    except Exception as e:
        logger.error(f"Error starting search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results")
async def get_results():
    """
    Get found channels that are pending (not yet processed/added).
    """
    try:
        params = {
            "filter[status][_eq]": "pending",
            "sort": "-subscription_priority",  # Show high priority first
            "limit": -1  # Get all pending
        }
        
        response = await directus.client.get("/items/found_channels", params=params)
        items = response.json().get('data', [])
        
        # Format for frontend
        results = []
        for item in items:
            results.append({
                "id": item.get("id"),
                "title": item.get("channel_title"),
                "username": item.get("channel_username"),
                "url": item.get("channel_url"),
                "subscribers": item.get("subscribers_count"),
                "priority": item.get("subscription_priority"),
                "posts_count": item.get("posts_with_comments", 0),
                "has_comments": item.get("has_comments_enabled", False),
                "keyword_id": item.get("search_keyword_id")
            })
            
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-to-monitoring")
async def add_to_monitoring(data: AddToMonitoringRequest):
    print("### ADD_TO_MONITORING VERSION 2025-12-12 ###")
    """
    Add selected channels to monitoring (channels collection).
    Update found_channels status to 'processed'.
    """
    try:
        added_count = 0
        skipped_count = 0
        errors = []
        
        logger.info(f"[Add to Monitoring] Received channel_ids: {data.channel_ids}")
        
        if not data.channel_ids:
            return {"added": 0, "skipped": 0, "errors": []}
            
        # Get details for selected channels
        # We process one by one to ensure safety (bulk operations might be tricky with simple client)
        for found_id in data.channel_ids:
            try:
                logger.info(f"[Add to Monitoring] Processing found_channel_id: {found_id}")
                
                # 1. Get found channel data
                found_item = await directus.get_item("found_channels", found_id)
                if not found_item:
                    logger.warning(f"[Add to Monitoring] Found channel {found_id} not found")
                    errors.append(f"Found channel {found_id} not found")
                    continue
                    
                # 2. Check if already in channels (avoid duplicates)
                # Check by found_channel_id instead of channel_url
                check_params = {
                    "filter[found_channel_id][_eq]": found_id,
                    "limit": 1
                }
                check_resp = await directus.client.get("/items/channels", params=check_params)
                existing = check_resp.json().get('data', [])
                
                if existing:
                    # Already exists, just mark as processed
                    logger.info(f"[Add to Monitoring] Channel with found_channel_id {found_id} already exists, skipping")
                    await directus.update_item("found_channels", found_id, {"status": "processed"})
                    skipped_count += 1
                    continue
                
                # 3. Create active channel with correct fields
                channel_data = {
                    "found_channel_id": found_id,  # M2O field key
                    "source": "search_parser",  # Map to work_mode in frontend
                    "status": "active",
                    "last_parsed_id": 0,
                    # url field is optional, UI gets it from found_channels relation
                }
                
                logger.info(f"[Add to Monitoring] Creating channel with payload: {channel_data}")
                
                created_item = await directus.create_item("channels", channel_data)
                created_id = created_item.get("id") if created_item else "unknown"
                logger.info(f"[Add to Monitoring] Created channel with id: {created_id}")
                
                # 4. Mark found channel as processed
                await directus.update_item("found_channels", found_id, {"status": "processed"})
                
                added_count += 1
                
            except Exception as inner_e:
                error_msg = f"Error processing channel {found_id}: {str(inner_e)}"
                logger.error(f"[Add to Monitoring] {error_msg}")
                errors.append(error_msg)
                continue
                
        return {
            "added": added_count,
            "skipped": skipped_count,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Error adding to monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))
