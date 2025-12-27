import os
import asyncpg
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_connection():
    """
    Создает пул соединений к PostgreSQL.
    Автоматически переключается на localhost при запуске вне Докера.
    """
    # 1. Читаем из ENV
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5433')
    user = os.getenv('POSTGRES_USER', 'neurocomment')
    password = os.getenv('POSTGRES_PASSWORD', 'Fh6YtNNmR76') # Хардкод для теста, потом из env
    database = os.getenv('POSTGRES_DB', 'neurocomment_db')

    # 2. ХАК ДЛЯ ЛОКАЛЬНОГО ТЕСТА
    # Если скрипт запущен на Windows (nt), а хост 'postgres' (докерный),
    # меняем его на localhost, чтобы подключиться снаружи.
    if os.name == 'nt' and host == 'postgres':
        print(f"⚠️  [Database] Меняю хост '{host}' на 'localhost' для Windows...")
        host = 'localhost'

    dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    # 3. Подключаемся БЕЗ SSL (критично для локалки)
    try:
        conn = await asyncpg.connect(dsn=dsn, ssl=False)
        yield conn
    except Exception as e:
        print(f"❌ [Database] Ошибка подключения к {host}:{port}: {e}")
        raise
    finally:
        if 'conn' in locals() and not conn.is_closed():
            await conn.close()
