import asyncio
import sys, os
sys.path.append(os.getcwd())
from backend.services.task_queue_manager import TaskQueueManager
from backend.services.task_scheduler import TaskScheduler # Если создавали
from backend.directus_client import DirectusClient

async def main():
    print("Наполняем очередь...")
    directus = DirectusClient()
    await directus.login()
    
    # Получаем аккаунты pending
    # (Тут упрощенно, лучше через TaskScheduler если он есть)
    tm = TaskQueueManager()
    await tm.create_task('setup_account', {'account_id': 123}, priority=10) # Тестовая задача
    
    print("Задача создана!")

if __name__ == "__main__":
    asyncio.run(main())
