#!/usr/bin/env python3
"""
Helper script to manually trigger the comment scheduler.
This script will run the schedule_comment_tasks method from TaskScheduler.
"""

import asyncio
import sys
import os

# Add the backend directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.task_scheduler import TaskScheduler


async def main():
    print("Starting comment scheduler...")
    
    try:
        # Create an instance of the scheduler
        scheduler = TaskScheduler()
        
        # Run the schedule_comment_tasks method
        tasks_created = await scheduler.schedule_comment_tasks()
        
        print(f"Comment scheduler completed. Created {tasks_created} tasks.")
        
    except Exception as e:
        print(f"Error running comment scheduler: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())