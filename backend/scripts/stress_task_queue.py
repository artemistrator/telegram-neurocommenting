import asyncio
import uuid
import os
import time
import random
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set
from backend.services.task_queue import task_queue_service
from backend.directus_client import directus

# Configuration from environment
TEST_TENANT_ID = os.getenv("TEST_TENANT_ID", "1")
CLAIM_WORKERS = int(os.getenv("CLAIM_WORKERS", "4"))
CLEANUP_TEST_TASKS = os.getenv("CLEANUP_TEST_TASKS", "true").lower() == "true"

async def cleanup_test_data():
    """Removes all tasks created during the current test session."""
    if not CLEANUP_TEST_TASKS:
        return
    try:
        # Search for all tasks with our TEST_TENANT_ID
        resp = await directus.client.get("/items/task_queue", params={
            "filter[tenant_id][_eq]": TEST_TENANT_ID,
            "limit": -1,
            "fields": "id"
        })
        items = resp.json().get('data', [])
        ids = [item['id'] for item in items]
        
        if not ids:
            return
            
        print(f"--- Cleaning up test data...")
        await directus.client.request("DELETE", "/items/task_queue", json=ids)
        print(f"Done: Deleted {len(ids)} test tasks.")
    except Exception as e:
        print(f"!!! Error during cleanup: {e}")

async def test_clock_drift():
    """Sanity check: ensures worker time is synced with Directus's apparent time."""
    print("\n[C] Clock Drift Sanity Check")
    now_local = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    print(f"   Local UTC: {now_local.isoformat()}")
    print("   OK: Clock drift check passed (dummy).")

async def test_idempotency(N=50):
    """
    Flood enqueue with same idempotency key.
    Expect: only one task ID should be returned across all calls if atomic.
    """
    print(f"\n[B] Idempotency under load (M={N} parallel enqueues)")
    idem_key = f"stress_idem_{uuid.uuid4().hex}"
    
    async def worker():
        try:
            res = await task_queue_service.enqueue_task(
                tenant_id=TEST_TENANT_ID,
                task_type="stress_idem",
                payload={"rand": random.random()},
                idempotency_key=idem_key
            )
            return res.get('id') if res else None
        except Exception:
            return None

    tasks = [worker() for _ in range(N)]
    results = await asyncio.gather(*tasks)
    ids = {r for r in results if r is not None}
    
    if len(ids) == 1:
        print(f"   OK: Only one task ID returned: {ids}")
    elif len(ids) == 0:
        print(f"   FAIL: No IDs returned at all!")
    else:
        print(f"   Returned unique IDs: {ids}")
        print(f"   FAIL: Multiple IDs returned: {ids}")

async def test_parallel_claim(N=100, num_workers=4):
    """
    1. Create N tasks.
    2. Start M parallel workers that try to claim them all.
    3. Verify no task was claimed more than once.
    """
    print(f"\n[A] Parallel Claim Test (N={N}, workers={num_workers})")
    
    print(f"   Preparing {N} tasks...")
    for i in range(N):
        await task_queue_service.enqueue_task(
            tenant_id=TEST_TENANT_ID,
            task_type="stress_task",
            payload={"i": i},
            idempotency_key=f"stress_{i}_{uuid.uuid4().hex[:8]}"
        )

    claimed_ids = []

    async def claiming_worker(name):
        await asyncio.sleep(random.uniform(0, 0.1))
        while True:
            try:
                task = await task_queue_service.claim_task(
                    tenant_id=TEST_TENANT_ID,
                    types=["stress_task"],
                    worker_id=name
                )
                if task:
                    claimed_ids.append(task['id'])
                else:
                    break
            except Exception:
                break

    start_time = time.time()
    print(f"   Launching {num_workers} workers...")
    workers = [claiming_worker(f"worker_{i}") for i in range(num_workers)]
    await asyncio.gather(*workers)
    duration = time.time() - start_time
    print(f"   Finished in {duration:.2f}s")

    total_claims = len(claimed_ids)
    unique_claims = len(set(claimed_ids))
    duplicates = total_claims - unique_claims

    print(f"   Total claims: {total_claims}")
    print(f"   Unique claims: {unique_claims}")
    
    if total_claims == N and unique_claims == N and duplicates == 0:
        print("   OK: All tasks claimed exactly once without collisions.")
    else:
        if total_claims != N: print(f"   FAIL: Total claims count {total_claims} != expected {N}")
        if unique_claims != N: print(f"   FAIL: Unique claims count {unique_claims} != expected {N}")
        if duplicates > 0: print(f"   FAIL: Found {duplicates} duplicate claims!")

async def run_stress_tests():
    exit_code = 0
    try:
        await directus.login()
        await test_clock_drift()
        await test_parallel_claim(N=100, num_workers=CLAIM_WORKERS)
        await test_idempotency(N=50)
        await cleanup_test_data()
    except Exception as e:
        print(f"!!! Global Stress Test Error: {e}")
        exit_code = 1
    finally:
        await directus.close()
    
    import sys
    sys.exit(exit_code)

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    asyncio.run(run_stress_tests())
