#!/usr/bin/env python3
"""
End-to-end integration test script to verify the new Task Queue architecture for subscriptions.

This script performs the following steps sequentially:
1. Environment Setup: Initialize DirectusClient, TaskScheduler, TaskQueueManager
2. Phase 1: Scheduling - Run TaskScheduler.schedule_subscriptions() and verify changes
3. Phase 2: Worker Execution - Simulate worker loop for ONE iteration
4. Phase 3: Final Verification - Check final status of subscription queue item
"""
import asyncio
import os
import sys
from datetime import datetime

# Add the backend directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.directus_client import directus
from backend.services.task_scheduler import TaskScheduler
from backend.services.task_queue_manager import TaskQueueManager


async def main():
    print("STEP 0: Environment Setup...")
    
    # Set DIRECTUS_URL to localhost for local testing if on Windows
    if os.name == 'nt':  # Windows check
        os.environ['DIRECTUS_URL'] = 'http://localhost:18055'
        print("  Set DIRECTUS_URL to http://localhost:18055 for local testing")
    
    # Initialize required components
    scheduler = TaskScheduler()
    task_queue_manager = TaskQueueManager()
    
    print("  Logging into Directus...")
    await directus.login()
    
    print("\nSTEP 1: Scheduling Phase...")
    print("  Running TaskScheduler.schedule_subscriptions()...")
    
    # Store initial state to compare later
    initial_tasks_response = await directus.safe_get("/items/task_queue", params={
        "filter[type][_eq]": "join_channel",
        "fields": "id,type,status,payload"
    })
    initial_tasks = initial_tasks_response.json().get('data', [])
    print(f"  Initial join_channel tasks count: {len(initial_tasks)}")
    
    # Run the scheduler
    created_count = await scheduler.schedule_subscriptions()
    print(f"  Created {created_count} join_channel tasks")
    
    # Find the most recent subscription_queue item that was pending
    pending_items_response = await directus.safe_get("/items/subscription_queue", params={
        "filter[status][_eq]": "processing",
        "sort": "-id",
        "limit": 1,
        "fields": "id,account_id,channel_url,found_channel_id,channel_id.id,channel_id.url,status"
    })
    pending_items = pending_items_response.json().get('data', [])
    
    if not pending_items:
        print("  ERROR: No subscription_queue items found with status 'processing'")
        return False
    
    subscription_item = pending_items[0]
    subscription_queue_id = subscription_item['id']
    print(f"  Found subscription_queue item #{subscription_queue_id} with status '{subscription_item['status']}'")
    
    # Verify new task appeared in task_queue with type='join_channel' and status='pending'
    new_tasks_response = await directus.safe_get("/items/task_queue", params={
        "filter[type][_eq]": "join_channel",
        "filter[status][_eq]": "pending",
        "sort": "-id",
        "limit": 10,  # Get recent tasks
        "fields": "id,type,status,payload,run_at"
    })
    new_tasks = new_tasks_response.json().get('data', [])
    
    join_channel_task = None
    for task in new_tasks:
        payload = task.get('payload', {})
        if payload.get('subscription_queue_id') == subscription_queue_id:
            join_channel_task = task
            break
    
    if not join_channel_task:
        print("  ERROR: No corresponding join_channel task found in task_queue")
        return False
    
    task_id = join_channel_task['id']
    print(f"  Found task: ID {task_id}, Type: {join_channel_task['type']}, Status: {join_channel_task['status']}")
    print(f"  Payload: {join_channel_task['payload']}")
    
    print(f"\nSTEP 2: Worker Execution Phase (Single Task)...")
    print(f"  Attempting to claim task with ID {task_id}...")
    
    # Claim the task as if a worker was processing it
    claimed_task = await task_queue_manager.claim_task(
        worker_id='test-worker',
        task_types=['join_channel']
    )
    
    if not claimed_task:
        print("  ERROR: No join_channel task was claimed - test failed")
        return False
    
    print(f"  Claimed task: ID {claimed_task['id']}, Type: {claimed_task['type']}")
    
    # Import and execute the join channel task processing logic
    # We'll replicate the logic from subscription_worker since importing might cause issues
    from backend.workers.subscription_worker import process_join_channel_task
    
    print("  Executing join channel task processing...")
    success = await process_join_channel_task(claimed_task)
    
    print(f"  Worker result: {'SUCCESS' if success else 'FAILED'}")
    
    print(f"\nSTEP 3: Final Verification...")
    print(f"  Fetching subscription_queue item #{subscription_queue_id} again...")
    
    # Fetch the original item from subscription_queue again
    updated_item_response = await directus.safe_get(f"/items/subscription_queue/{subscription_queue_id}")
    updated_item = updated_item_response.json().get('data')
    
    if not updated_item:
        print(f"  ERROR: Could not fetch subscription_queue item #{subscription_queue_id}")
        return False
    
    final_status = updated_item['status']
    print(f"  Final status: {final_status}")
    
    # Also check the task status in task_queue
    task_response = await directus.safe_get(f"/items/task_queue/{task_id}")
    task_data = task_response.json().get('data')
    task_status = task_data['status'] if task_data else 'not_found'
    print(f"  Final task status: {task_status}")
    
    if final_status == 'subscribed':
        print(f"\nSUCCESS: Subscription flow completed for Item #{subscription_queue_id}")
        print(f"  - Subscription queue item status: {final_status}")
        print(f"  - Task queue item status: {task_status}")
        return True
    else:
        print(f"\nFAILURE: Subscription flow did not complete as expected")
        print(f"  - Expected status: 'subscribed', Got: '{final_status}'")
        print(f"  - Task queue item status: {task_status}")
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        if result:
            print("\nIntegration test PASSED!")
            sys.exit(0)
        else:
            print("\nIntegration test FAILED!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nIntegration test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nIntegration test ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)