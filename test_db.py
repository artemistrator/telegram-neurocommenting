import sys
import os
sys.path.append(os.getcwd())
import asyncio
import os
# Импортируем нашу функцию из database.py
from backend.database import get_db_connection

async def test_connection():
    print("⏳ Пробую подключиться к PostgreSQL...")
    
    # Пытаемся взять настройки из ENV, чтобы видеть, куда стучимся
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    database = os.getenv('POSTGRES_DB', 'neurocomment')
    
    print(f"🌍 Хост: {host}")
    
    # For testing, hardcode host to localhost and print the DSN
    test_host = 'localhost'
    masked_dsn = f"postgresql://{user}:***@{test_host}:{port}/{database}"
    print(f"🔗 Используемый DSN: {masked_dsn}")

    # Update the environment temporarily for the connection
    original_host = os.getenv('POSTGRES_HOST')
    os.environ['POSTGRES_HOST'] = test_host
    
    try:
        async with get_db_connection() as conn:
            print("✅ Успешно подключились!")
            
            # Проверим, видит ли он таблицу task_queue
            version = await conn.fetchval('SELECT version();')
            print(f"📦 Версия базы: {version}")
            
            rows = await conn.fetchval("SELECT count(*) FROM task_queue;")
            print(f"📊 В таблице task_queue сейчас задач: {rows}")
            
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        print("💡 Совет: Проверь логин/пароль в .env и запущен ли Docker.")
    finally:
        # Restore original host
        if original_host is not None:
            os.environ['POSTGRES_HOST'] = original_host
        else:
            # If original was not set, remove the env var
            if 'POSTGRES_HOST' in os.environ:
                del os.environ['POSTGRES_HOST']

if __name__ == "__main__":
    asyncio.run(test_connection())
