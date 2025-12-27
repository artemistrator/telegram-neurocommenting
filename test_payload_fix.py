import asyncio
import json
from datetime import datetime
from backend.services.task_queue_manager import TaskQueueManager
from backend.database import get_db_connection


async def test_payload_fix():
    print("Testing payload JSON parsing fix...")
    
    # Create a task queue manager
    task_manager = TaskQueueManager()
    
    # Create a test task with a payload
    test_payload = {'account_id': 789, 'test_data': 'test_value', 'nested': {'key': 'value'}}
    print(f"Creating task with payload: {test_payload}")
    
    task_id = await task_manager.create_task(
        task_type='setup_account',
        payload=test_payload,
        run_at=None,  # Immediate execution
        priority=1,
        max_attempts=3
    )
    print(f"Created task with ID: {task_id}")
    
    # Verify the task was created and check how payload is stored in DB
    async with get_db_connection() as conn:
        raw_task = await conn.fetchrow("SELECT payload FROM task_queue WHERE id = $1", task_id)
        print(f"Raw payload from DB: {raw_task['payload']} (type: {type(raw_task['payload'])})")
    
    # Now claim the task - this should parse the JSON payload
    print("Attempting to claim the task with JSON parsing...")
    claimed_task = await task_manager.claim_task('test-worker-payload', ['setup_account'])
    
    if claimed_task:
        print(f"SUCCESS: Claimed task {claimed_task['id']} of type {claimed_task['type']}")
        print(f"Task status: {claimed_task['status']}")
        print(f"Payload type: {type(claimed_task['payload'])}")
        print(f"Payload content: {claimed_task['payload']}")
        
        # Test accessing the payload as a dict (this was failing before)
        payload = claimed_task['payload']
        account_id = payload.get('account_id')
        print(f"Successfully accessed account_id: {account_id}")
        
        # Complete the task to clean up
        await task_manager.complete_task(task_id)
        print("Completed the test task")
    else:
        print("FAILED: Could not claim the task")


if __name__ == "__main__":
    asyncio.run(test_payload_fix())