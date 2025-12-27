#!/usr/bin/env python3
"""
Helper script to trigger subscription scheduling manually for testing.
"""
import asyncio
import sys
import os

# Add the backend directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.task_scheduler import TaskScheduler
from backend.directus_client import directus


async def main():
    print("Initializing TaskScheduler...")
    scheduler = TaskScheduler()
    
    print("Logging into Directus...")
    await directus.login()
    
    print("Scheduling subscriptions...")
    created_count = await scheduler.schedule_subscriptions()
    
    print(f"Subscription scheduling completed. Created {created_count} tasks.")
    

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
    except Exception as e:
        print(f"Error running subscription scheduler: {e}")
        import traceback
        traceback.print_exc()