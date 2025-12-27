#!/usr/bin/env python3
"""
Helper script to manually trigger the listener task scheduler.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.task_scheduler import TaskScheduler


async def main():
    """Main function to run the listener scheduler."""
    print("🚀 Running Listener Task Scheduler...")
    
    try:
        # Initialize the task scheduler
        scheduler = TaskScheduler()
        
        # Run the listener scheduler
        tasks_created = await scheduler.schedule_listener_tasks()
        
        print(f"✅ Completed! Created {tasks_created} fetch_posts tasks")
        
    except Exception as e:
        print(f"❌ Error running listener scheduler: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)