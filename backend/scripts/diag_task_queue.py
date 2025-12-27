import asyncio
import json
from datetime import datetime, timezone, timedelta
from backend.directus_client import directus

async def diag():
    print(">>> Starting Task Queue Diagnostics...")
    await directus.login()
    
    resp = await directus.client.get("/items/task_queue", params={"limit": 1})
    tasks = resp.json().get('data', [])
    
    if not tasks:
        print("No tasks found, creating one...")
        await directus.client.post("/items/task_queue", json={
            "tenant_id": 1,
            "type": "diag_task",
            "status": "pending",
            "run_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        })
        resp = await directus.client.get("/items/task_queue", params={"limit": 1})
        tasks = resp.json().get('data', [])

    if tasks:
        t0 = tasks[0]
        tid = t0['id']
        print(f"\n--- Testing PATCH syntax for ID={tid} (status={t0['status']}):")
        
        # Style 4: Combined body (data + query)
        print("\nStyle 4: Combined body (data + query) - SHOULD MATCH")
        body4 = {
            "data": {"priority": t0.get('priority', 0)},
            "query": {"filter": {"id": {"_eq": tid}, "status": {"_eq": t0['status']}}}
        }
        resp4 = await directus.client.patch("/items/task_queue", json=body4)
        print(f"Style 4 result: {resp4.status_code} updated count: {len(resp4.json().get('data', []))}")

        # Style 10: Parallel Race Test
        print("\nStyle 10: Parallel Race Test (2 workers, same ID)...")
        # Reset to pending
        await directus.client.patch(f"/items/task_queue/{tid}", json={"status": "pending"})
        
        async def mock_worker(name):
            body = {
                "data": {"status": "processing", "locked_by": name},
                "query": {"filter": {"id": {"_eq": tid}, "status": {"_eq": "pending"}}}
            }
            resp = await directus.client.patch("/items/task_queue", json=body)
            d = resp.json().get('data', [])
            print(f"   Worker {name} result: {resp.status_code} updated count: {len(d)}")
            return len(d)

        # Style 12: Single item GET check
        print("\nStyle 12: Single item GET check...")
        resp12 = await directus.client.get(f"/items/task_queue/{tid}")
        print(f"Style 12 result: {resp12.status_code}")
        print(f"Response data type: {type(resp12.json().get('data'))}")
        print(f"Data sample: {json.dumps(resp12.json().get('data'), indent=2)[:200]}...")

if __name__ == "__main__":
    asyncio.run(diag())
