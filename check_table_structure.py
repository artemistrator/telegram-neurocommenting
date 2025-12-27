import sys
import os
sys.path.append(os.getcwd())
import asyncio
import os
from backend.database import get_db_connection

async def check_table_structure():
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
            
            # Get column information for task_queue table
            result = await conn.fetch('''
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'task_queue' 
                ORDER BY ordinal_position;
            ''')
            
            print('task_queue table structure:')
            for row in result:
                print(f'  {row["column_name"]}: {row["data_type"]} (nullable: {row["is_nullable"]}, default: {row["column_default"]})')
            
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
    asyncio.run(check_table_structure())