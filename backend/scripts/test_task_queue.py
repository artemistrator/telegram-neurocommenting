import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from backend.services.task_queue import task_queue_service
from backend.directus_client import directus

async def test_task_queue():
    print(">>> Starting Task Queue Test...")
    
    tenant_id = 1
    task_type = "test_task"
    idempotency_key = str(uuid.uuid4())
    worker_id = "test_worker_1"
    
    try:
        # 0. Login
        await directus.login()
        
        # 1. Enqueue Task
        print(f"--- Enqueuing task with idempotency_key: {idempotency_key}...")
        task = await task_queue_service.enqueue_task(
            tenant_id=tenant_id,
            task_type=task_type,
            payload={"test_data": "hello"},
            idempotency_key=idempotency_key,
            priority=10,
            run_at=datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        print(f"[OK] Task created/found: ID={task['id']}, Status={task['status']}")

        # 2. Claim Task
        print(f"--- Claiming task for worker: {worker_id}...")
        claimed_task = await task_queue_service.claim_task(
            tenant_id=tenant_id,
            types=[task_type],
            worker_id=worker_id,
            lease_seconds=30
        )
        
        if claimed_task:
            print(f"[OK] Task claimed: ID={claimed_task['id']}")
            
            # 3. Log Event
            print("--- Logging event...")
            await task_queue_service.log_event(
                task_id=claimed_task['id'],
                tenant_id=tenant_id,
                level="info",
                event="worker_started",
                message="Worker started processing the task",
                data={"worker": worker_id}
            )
            
            # 4. Complete Task
            print("--- Completing task...")
            completed_task = await task_queue_service.complete_task(
                task_id=claimed_task['id'],
                result={"status": "all_good"}
            )
            print(f"[OK] Task completed: ID={completed_task['id']}, Status={completed_task['status']}")
        else:
            print("[FAIL] Failed to claim task (maybe someone else took it or filters didn't match)")

        # 4. Fail Task
        print("--- Testing task failure/retry...")
        task_fail = await task_queue_service.enqueue_task(
            tenant_id=tenant_id,
            task_type="fail_item",
            payload={"error": "test"},
            idempotency_key=str(uuid.uuid4()),
            run_at=datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        claimed_fail = await task_queue_service.claim_task(tenant_id, ["fail_item"], "worker_2")
        if not claimed_fail:
             raise Exception("Failed to claim task for failure test")
        print(f"[OK] Claimed for failure test: ID={claimed_fail['id']}")
        await task_queue_service.fail_task(claimed_fail['id'], error="Something went wrong", retry_in_seconds=5)
        
        # Verify it's back to pending
        updated_fail = await directus.get_item("task_queue", claimed_fail['id'])
        print(f"[OK] Task ID={claimed_fail['id']} status after fail: {updated_fail['status']} (attempts: {updated_fail['attempts']})")

        # 5. Release Expired Leases
        print("--- Testing lease release...")
        # Artificially create a processing task with expired lock
        task_expired = await task_queue_service.enqueue_task(
            tenant_id=tenant_id,
            task_type="expired_item",
            payload={"expired": True},
            idempotency_key=str(uuid.uuid4()),
            run_at=datetime.now(timezone.utc) - timedelta(minutes=20)
        )
        # Manually set it to processing with expired lock (naive ISO like DirectusClient._now_str)
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        await directus.update_item("task_queue", task_expired['id'], {
            "status": "processing",
            "locked_until": (now_naive - timedelta(minutes=1)).isoformat()
        })
        
        released_count = await task_queue_service.release_expired_leases(tenant_id=tenant_id)
        print(f"[OK] Released {released_count} expired tasks")
        
        # Verify it's pending again
        final_expired = await directus.get_item("task_queue", task_expired['id'])
        print(f"[OK] Task ID={task_expired['id']} status after release: {final_expired['status']}")

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await directus.close()

if __name__ == "__main__":
    asyncio.run(test_task_queue())
