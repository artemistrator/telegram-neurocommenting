import asyncio
import json
from backend.services.task_queue_manager import TaskQueueManager


async def test_setup_worker_payload():
    print("Testing setup worker payload access...")
    
    # Create a task queue manager
    task_manager = TaskQueueManager()
    
    # Create a test task similar to what setup worker would process
    test_payload = {'account_id': 999, 'setup_data': 'some_setup_info'}
    print(f"Creating setup task with payload: {test_payload}")
    
    task_id = await task_manager.create_task(
        task_type='setup_account',
        payload=test_payload,
        run_at=None,
        priority=1,
        max_attempts=3
    )
    print(f"Created setup task with ID: {task_id}")
    
    # Claim the task (this simulates what setup worker does)
    claimed_task = await task_manager.claim_task('setup-test-worker', ['setup_account'])
    
    if claimed_task:
        print(f"Claimed task: {claimed_task['id']}")
        
        # Simulate the setup worker code that was failing
        # Original problematic code from setup_worker.py:
        payload = claimed_task.get('payload', {})
        print(f"Payload type: {type(payload)}")
        print(f"Payload content: {payload}")
        
        # This was the line that was failing: payload.get('account_id')
        account_id = payload.get('account_id')
        print(f"Successfully extracted account_id: {account_id}")
        
        if not account_id:
            print("ERROR: account_id is missing!")
        else:
            print("SUCCESS: setup worker code will work correctly now!")
        
        # Complete the task to clean up
        await task_manager.complete_task(task_id)
        print("Completed the test task")
    else:
        print("FAILED: Could not claim the task")


if __name__ == "__main__":
    asyncio.run(test_setup_worker_payload())