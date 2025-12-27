from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Any, Dict
from backend.services.task_queue import task_queue_service
from backend.directus_client import directus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.get("/")
async def list_tasks(
    tenant_id: str,
    status: Optional[str] = None,
    task_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Get a list of tasks with filters.
    """
    params = {
        "filter[tenant_id][_eq]": tenant_id,
        "limit": limit,
        "sort": "-date_created"
    }
    if status:
        params["filter[status][_eq]"] = status
    if task_type:
        params["filter[type][_eq]"] = task_type
        
    try:
        response = await directus.client.get("/items/task_queue", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}")
async def get_task_details(task_id: Any):
    """
    Get task details and its recent events.
    """
    task = await directus.get_item("task_queue", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # Get last 10 events for this task
    try:
        events_resp = await directus.client.get("/items/task_events", params={
            "filter[task_id][_eq]": task_id,
            "sort": "-timestamp",
            "limit": 10
        })
        events_resp.raise_for_status()
        events = events_resp.json().get('data', [])
    except Exception as e:
        events = []
        print(f"Error fetching events for task {task_id}: {e}")
        
    return {
        "task": task,
        "events": events
    }
