import asyncio
import json
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from backend.directus_client import directus

class TaskQueue:
    def __init__(self, client=directus):
        self.client = client

    def _now_str(self) -> str:
        """Returns current UTC time in ISO format (naive, no microseconds) for Directus compat."""
        # SQLite/Directus often prefer YYYY-MM-DDTHH:MM:SS
        return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()

    async def _get_existing_task(self, tenant_id: Any, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Helper to find an existing task by tenant and idempotency key."""
        try:
            # Using JSON filter for multiple conditions is more robust
            filter_obj = {
                "_and": [
                    {"tenant_id": {"_eq": tenant_id}},
                    {"idempotency_key": {"_eq": idempotency_key}}
                ]
            }
            params = {
                "filter": json.dumps(filter_obj),
                "limit": 1
            }
            resp = await self.client.client.get("/items/task_queue", params=params)
            data = resp.json().get('data', [])
            return data[0] if data else None
        except Exception as e:
            print(f"DEBUG _get_existing_task error: {e}")
            return None

    async def enqueue_task(
        self, 
        tenant_id: Any, 
        task_type: str, 
        payload: Dict[str, Any], 
        idempotency_key: str,
        run_at: Optional[datetime] = None, 
        priority: int = 0, 
        max_attempts: int = 5
    ) -> Dict[str, Any]:
        """
        Enqueues a task or returns an existing one.
        Check -> Create -> re-check.
        """
        existing = await self._get_existing_task(tenant_id, idempotency_key)
        if existing:
            return existing

        run_at_str = run_at.replace(tzinfo=None, microsecond=0).isoformat() if run_at else self._now_str()
        new_task = {
            "tenant_id": tenant_id,
            "type": task_type,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "status": "pending",
            "priority": priority,
            "max_attempts": max_attempts,
            "attempts": 0,
            "run_at": run_at_str
        }

        try:
            return await self.client.create_item("task_queue", new_task)
        except Exception:
            final_check = await self._get_existing_task(tenant_id, idempotency_key)
            if final_check:
                return final_check
            raise

    async def claim_task(
        self, 
        tenant_id: Any, 
        types: List[str], 
        worker_id: str, 
        lease_seconds: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Attempts to claim a task using an atomic conditional PATCH.
        """
        now_str = self._now_str()
        pick_time = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=2)).replace(microsecond=0).isoformat()
        
        # Simplify candidate fetching to be more compatible
        params = {
            "filter[tenant_id][_eq]": tenant_id,
            "filter[status][_eq]": "pending",
            "filter[run_at][_lte]": pick_time,
            "sort": "-priority,run_at",
            "limit": 50,
            "fields": "id,status,locked_until"
        }
        
        if types:
            if len(types) == 1:
                params["filter[type][_eq]"] = types[0]
            else:
                for i, t in enumerate(types):
                    params[f"filter[type][_in][{i}]"] = t

        try:
            resp = await self.client.client.get("/items/task_queue", params=params)
            candidates = resp.json().get('data', [])
        except Exception:
            return None

        if not candidates:
            return None

        # Randomize candidates to reduce contention between parallel workers
        import random
        random.shuffle(candidates)

        for cand in candidates:
            # Client-side filtering for lock
            lu = cand.get('locked_until')
            if lu and lu >= now_str:
                continue

            tid = cand['id']
            locked_until_new = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=lease_seconds)).replace(microsecond=0).isoformat()
            
            # Atomic conditional filter
            patch_filter = {
                "_and": [
                    {"id": {"_eq": tid}},
                    {"tenant_id": {"_eq": tenant_id}},
                    {"status": {"_eq": "pending"}}
                ]
            }
            if lu:
                patch_filter["_and"].append({"locked_until": {"_eq": lu}})
            else:
                patch_filter["_and"].append({"locked_until": {"_null": True}})

            try:
                patch_resp = await self.client.client.patch(
                    "/items/task_queue", 
                    json={
                        "data": {
                            "status": "processing",
                            "locked_by": worker_id,
                            "locked_until": locked_until_new,
                            "processing_started_at": self._now_str()
                        },
                        "query": {"filter": patch_filter}
                    }
                )
                if patch_resp.status_code == 200:
                    data = patch_resp.json().get('data')
                    if data and isinstance(data, list) and len(data) > 0:
                        # Re-verify claim with cache busting to bypass potential Directus stale data
                        # We use uuid.uuid4().hex as a cache buster
                        v_resp = await self.client.client.get(f"/items/task_queue/{tid}", params={"_cb": uuid.uuid4().hex})
                        if v_resp.status_code == 200:
                            item = v_resp.json().get('data', {})
                            if item.get('locked_by') == worker_id and item.get('status') == "processing":
                                return item
                elif patch_resp.status_code >= 400:
                    # Log unexpected API errors only
                    pass
            except Exception:
                continue
                
        return None

    async def complete_task(self, task_id: Any, result: Any = None) -> Dict[str, Any]:
        """Marks task as completed."""
        return await self.client.update_item("task_queue", task_id, {
            "status": "completed",
            "result": result,
            "locked_until": None,
            "processing_finished_at": self._now_str()
        })

    async def fail_task(self, task_id: Any, error: str, retry_in_seconds: Optional[int] = None) -> Dict[str, Any]:
        """Handles task failure with retry logic."""
        task = await self.client.get_item("task_queue", task_id)
        if not task:
            raise Exception(f"Task {task_id} not found")

        attempts = (task.get('attempts') or 0) + 1
        max_attempts = task.get('max_attempts') or 5
        
        update_data = {
            "attempts": attempts,
            "last_error": error,
            "locked_until": None
        }

        if retry_in_seconds is not None and attempts < max_attempts:
            update_data["status"] = "pending"
            update_data["run_at"] = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=retry_in_seconds)).replace(microsecond=0).isoformat()
        else:
            update_data["status"] = "dead" if attempts >= max_attempts else "failed"

        return await self.client.update_item("task_queue", task_id, update_data)

    async def log_event(
        self, task_id: Any, tenant_id: Any, level: str, event: str, message: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Logs an event to task_events."""
        return await self.client.create_item("task_events", {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "level": level,
            "event": message, # Wait, the field name is 'event' but I should probably use the event value
            # Actually, looking at routers/tasks.py, it uses task_events.
            "event": event,
            "message": message,
            "data": data
        })

    async def release_expired_leases(self, tenant_id: Optional[Any] = None) -> int:
        """Resets expired stuck 'processing' tasks."""
        now_str = self._now_str()
        filter_obj = {
            "_and": [
                {"status": {"_eq": "processing"}},
                {"locked_until": {"_lt": now_str}}
            ]
        }
        if tenant_id:
            filter_obj["_and"].append({"tenant_id": {"_eq": tenant_id}})
            
        try:
            resp = await self.client.client.patch(
                "/items/task_queue", 
                json={
                    "data": {"status": "pending", "locked_by": None, "locked_until": None},
                    "query": {"filter": filter_obj}
                }
            )
            data = resp.json().get('data', [])
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0

task_queue_service = TaskQueue()
