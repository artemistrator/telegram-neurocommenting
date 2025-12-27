import asyncio
import json
from datetime import datetime
from backend.services.task_queue_manager import TaskQueueManager
from backend.database import get_db_connection


async def simple_test_claim_task():
    print("Simple test for claim_task fix...")
    
    # Create a task queue manager
    task_manager = TaskQueueManager()
    
    # First, let's create a test task
    print("Creating a test task...")
    task_id = await task_manager.create_task(
        task_type='setup_account',
        payload={'account_id': 123, 'test': True},
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
    
    # Now try to claim the task with the fixed logic (without calling log_event)
    print("Attempting to claim the task...")
    
    # Let's execute the same query that claim_task does directly to test it
    async with get_db_connection() as conn:
        # Build the query with the fixed logic
        where_conditions = ["status = 'pending'", "(run_at IS NULL OR run_at <= NOW())", "type = ANY(ARRAY[$2])"]
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
            UPDATE task_queue
            SET 
                status = 'processing',
                locked_by = $1,
                locked_until = NOW() + INTERVAL '5 minutes',
                processing_started_at = NOW()
            WHERE id = (
                SELECT id
                FROM task_queue
                WHERE {where_clause}
                ORDER BY priority DESC, date_created ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
        """
        
        # Execute the query
        row = await conn.fetchrow(query, 'test-worker', 'setup_account')
        
        if row:
            print(f"SUCCESS: Claimed task {row['id']} of type {row['type']}")
            print(f"Task status: {row['status']}")
            print(f"Locked by: {row['locked_by']}")
            print(f"Locked until: {row['locked_until']}")
            
            # Complete the task to clean up
            update_query = """
                UPDATE task_queue
                SET 
                    status = 'done',
                    processing_started_at = NULL,
                    locked_by = NULL,
                    locked_until = NULL
                WHERE id = $1
                RETURNING id
            """
            result_row = await conn.fetchrow(update_query, task_id)
            print("Completed the test task")
        else:
            print("FAILED: Could not claim the task")
            
            # Let's check if there are any pending tasks
            pending_tasks = await conn.fetch("SELECT * FROM task_queue WHERE status = 'pending' AND type = 'setup_account'")
            print(f"Found {len(pending_tasks)} pending setup_account tasks")
            for task in pending_tasks:
                print(f"  Task ID: {task['id']}, run_at: {task['run_at']}, priority: {task['priority']}")


if __name__ == "__main__":
    asyncio.run(simple_test_claim_task())