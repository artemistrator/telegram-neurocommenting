import asyncio
import json
from datetime import datetime
from backend.services.task_queue_manager import TaskQueueManager
from backend.database import get_db_connection


async def test_updated_claim_task():
    print("Testing updated claim_task method...")
    
    # Create a task queue manager
    task_manager = TaskQueueManager()
    
    # First, let's create a test task
    print("Creating a test task...")
    task_id = await task_manager.create_task(
        task_type='setup_account',
        payload={'account_id': 456, 'test': True},
        run_at=None,  # Immediate execution
        priority=1,
        max_attempts=3
    )
    print(f"Created task with ID: {task_id}")
    
    # Verify the task was created with pending status
    async with get_db_connection() as conn:
        task = await conn.fetchrow("SELECT * FROM task_queue WHERE id = $1", task_id)
        print(f"Task status after creation: {task['status']}")
        print(f"Task type: {task['type']}")
        print(f"Task run_at: {task['run_at']}")
    
    # Now try to claim the task with the updated method
    print("Attempting to claim the task with updated method...")
    claimed_task = await task_manager.claim_task('test-worker-updated', ['setup_account'])
    
    if claimed_task:
        print(f"SUCCESS: Claimed task {claimed_task['id']} of type {claimed_task['type']}")
        print(f"Task status: {claimed_task['status']}")
        print(f"Locked by: {claimed_task['locked_by']}")
        print(f"Locked until: {claimed_task['locked_until']}")
        
        # Complete the task to clean up
        await task_manager.complete_task(task_id)
        print("Completed the test task")
    else:
        print("FAILED: Could not claim the task")
        
        # Let's check if there are any pending tasks
        async with get_db_connection() as conn:
            pending_tasks = await conn.fetch("SELECT * FROM task_queue WHERE status = 'pending' AND type = 'setup_account'")
            print(f"Found {len(pending_tasks)} pending setup_account tasks")
            for task in pending_tasks:
                print(f"  Task ID: {task['id']}, run_at: {task['run_at']}, priority: {task['priority']}")


if __name__ == "__main__":
    asyncio.run(test_updated_claim_task())