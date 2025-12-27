import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import asyncpg

from backend.database import get_db_connection

class TaskQueueManager:
    def __init__(self):
        pass

    async def create_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        run_at: Optional[datetime] = None,
        priority: int = 0,
        max_attempts: int = 3
    ) -> int:
        """
        Create a new task in the task queue.
        
        Args:
            task_type: Type of task (e.g., 'join_channel', 'ingest_post', etc.)
            payload: Task-specific data
            run_at: When the task should run (None for immediate)
            priority: Priority of the task (higher number = higher priority)
            max_attempts: Maximum number of attempts before failing
        
        Returns:
            ID of the created task
        """
        if run_at is None:
            run_at = datetime.utcnow()
        
        async with get_db_connection() as conn:
            query = """
                INSERT INTO task_queue (
                    status, type, payload, run_at, priority, attempts, max_attempts
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """
            task_id = await conn.fetchval(
                query,
                'pending',
                task_type,
                json.dumps(payload),
                run_at,
                priority,
                0,  # attempts start at 0
                max_attempts
            )
            return task_id

    async def claim_task(
        self,
        worker_id: str,
        task_types: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Claim a task for processing. Uses transactional UPDATE with FOR UPDATE SKIP LOCKED
        to atomically select and lock the highest priority task.
        
        Args:
            worker_id: Unique identifier for the worker claiming the task
            task_types: Optional list of task types to filter by
        
        Returns:
            Task dict if available, None otherwise
        """
        print(f"Claiming task types: {task_types}")
        
        async with get_db_connection() as conn:
            # Build the query with the exact logic from the working test
            where_conditions = ["status = 'pending'", "(run_at IS NULL OR run_at <= NOW())"]
            
            if task_types:
                # Use the parameterized array approach to handle the task types list
                placeholders = ",".join([f"${i+2}" for i in range(len(task_types))])
                where_conditions.append(f"type = ANY(ARRAY[{placeholders}])")
            
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
            
            # Build parameters
            params = [worker_id]
            if task_types:
                params.extend(task_types)
            
            # Execute the query
            row = await conn.fetchrow(query, *params)
            
            if row:
                # Parse JSON fields that come as strings from the database
                result = dict(row)  # Convert asyncpg Record to dict
                
                # Parse payload if it's a string
                if 'payload' in result and isinstance(result['payload'], str):
                    try:
                        result['payload'] = json.loads(result['payload'])
                    except json.JSONDecodeError:
                        # If JSON parsing fails, keep original value and log warning
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to parse JSON payload for task {result.get('id', 'unknown')}: {result['payload']}")
                
                # Parse result if it's a string
                if 'result' in result and result['result'] is not None and isinstance(result['result'], str):
                    try:
                        result['result'] = json.loads(result['result'])
                    except json.JSONDecodeError:
                        # If JSON parsing fails, keep original value and log warning
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to parse JSON result for task {result.get('id', 'unknown')}: {result['result']}")
                
                return result
            
            return None

    async def complete_task(
        self,
        task_id: int,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: ID of the task to complete
            result: Optional result data to store
        
        Returns:
            True if successful, False otherwise
        """
        async with get_db_connection() as conn:
            query = """
                UPDATE task_queue
                SET 
                    status = 'done',
                    result = $2,
                    processing_started_at = NULL,
                    locked_by = NULL,
                    locked_until = NULL
                WHERE id = $1
                RETURNING id
            """
            result_row = await conn.fetchrow(query, task_id, json.dumps(result) if result else None)
            
            if result_row:
                await self.log_event(
                    task_id,
                    'info',
                    'done',
                    'Task completed successfully'
                )
                return True
            
            return False

    async def fail_task(
        self,
        task_id: int,
        error_message: str
    ) -> bool:
        """
        Mark a task as failed, with potential retry logic.
        
        Args:
            task_id: ID of the task to fail
            error_message: Error message to log
        
        Returns:
            True if successful, False otherwise
        """
        async with get_db_connection() as conn:
            # Get current task info
            task_query = """
                SELECT attempts, max_attempts
                FROM task_queue
                WHERE id = $1
            """
            task_row = await conn.fetchrow(task_query, task_id)
            
            if not task_row:
                return False
            
            attempts = task_row['attempts']
            max_attempts = task_row['max_attempts']
            
            if attempts < max_attempts - 1:  # -1 because attempts starts at 0
                # Schedule retry with exponential backoff
                # Backoff intervals: 1 min, 5 min, 25 min, etc.
                backoff_seconds = 60 * (5 ** attempts)
                next_run_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
                
                update_query = """
                    UPDATE task_queue
                    SET 
                        status = 'pending',
                        attempts = attempts + 1,
                        run_at = $2,
                        last_error = $3,
                        processing_started_at = NULL,
                        locked_by = NULL,
                        locked_until = NULL
                    WHERE id = $1
                    RETURNING id
                """
                result_row = await conn.fetchrow(update_query, task_id, next_run_at, error_message)
                
                if result_row:
                    await self.log_event(
                        task_id,
                        'warning',
                        'retry_scheduled',
                        f'Task retry scheduled in {backoff_seconds} seconds (attempt {attempts + 1}/{max_attempts})'
                    )
                    return True
            else:
                # Mark as failed/dead
                update_query = """
                    UPDATE task_queue
                    SET 
                        status = 'failed',
                        attempts = attempts + 1,
                        last_error = $2,
                        processing_started_at = NULL,
                        locked_by = NULL,
                        locked_until = NULL
                    WHERE id = $1
                    RETURNING id
                """
                result_row = await conn.fetchrow(update_query, task_id, error_message)
                
                if result_row:
                    await self.log_event(
                        task_id,
                        'error',
                        'failed',
                        f'Task failed after {max_attempts} attempts: {error_message}'
                    )
                    return True
            
            return False

    async def log_event(
        self,
        task_id: int,
        level: str,
        event: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Log an event for a task.
        
        Args:
            task_id: ID of the task
            level: Log level ('debug', 'info', 'warning', 'error')
            event: Event type
            message: Log message
            data: Optional additional data to store
        
        Returns:
            ID of the created event
        """
        async with get_db_connection() as conn:
            query = """
                INSERT INTO task_events (
                    task_id, level, event, message, data, date_created
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING id
            """
            event_id = await conn.fetchval(
                query,
                task_id,
                level,
                event,
                message,
                json.dumps(data) if data else None
            )
            return event_id