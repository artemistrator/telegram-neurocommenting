import asyncio
import sys
import os

# Добавляем текущую папку в путь, чтобы видеть пакет backend
sys.path.append(os.getcwd())

from backend.database import get_db_connection

async def main():
    print("🚀 Тест подключения...")
    try:
        async with get_db_connection() as conn:
            print("✅ ПОДКЛЮЧЕНИЕ ЕСТЬ!")
            res = await conn.fetchval("SELECT 'Postgres is alive!'")
            print(f"💬 Ответ базы: {res}")
            
            # Проверим таблицу task_queue
            count = await conn.fetchval("SELECT count(*) FROM task_queue")
            print(f"tasks в очереди: {count}")
            
    except Exception as e:
        print(f"💀 Всё плохо: {e}")

if __name__ == "__main__":
    asyncio.run(main())
