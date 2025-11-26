# Script to integrate subscriber module into main.py
import re

# Read the original main.py
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports after line 14 (after "from account_manager import AccountManager")
imports_to_add = """from database import init_database, migrate_from_json, get_setting, set_setting
from subscriber import add_channels_to_queue, process_subscription_queue, get_subscription_stats
"""

content = content.replace(
    "from account_manager import AccountManager",
    f"from account_manager import AccountManager\n{imports_to_add}"
)

# 2. Add Pydantic models after MonitoringSettings
models_to_add = """
class ChannelListRequest(BaseModel):
    channel_urls: List[str]

class LimitsSettings(BaseModel):
    max_subs_per_day: int
    delay_min_seconds: int
    delay_max_seconds: int
"""

content = content.replace(
    "class MonitoringSettings(BaseModel):\n    min_words: int = 5\n    use_triggers: bool = True\n    trigger_words: List[str] = []",
    f"class MonitoringSettings(BaseModel):\n    min_words: int = 5\n    use_triggers: bool = True\n    trigger_words: List[str] = []\n{models_to_add}"
)

# 3. Replace startup_event function
old_startup = '''# Startup event
@app.on_event("startup")
async def startup_event():
    global telegram_config
    
    print("Запуск приложения...")
    
    # Только загрузить config.json - БЕЗ подключения к Telegram
    if os.path.exists('config.json'):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if 'telegram' in config_data:
                telegram_config.update(config_data['telegram'])
                print("Конфигурация загружена из config.json")
        except Exception as e:
            print(f"Ошибка загрузки config.json: {e}")
    
    print("Приложение готово к работе")'''

new_startup = '''# Startup event
@app.on_event("startup")
async def startup_event():
    global telegram_config
    
    print("Запуск приложения...")
    
    # Initialize database
    try:
        await init_database()
        print("База данных инициализирована")
        
        # Migrate from accounts.json if exists
        migration_result = await migrate_from_json()
        if migration_result['status'] == 'success':
            print(f"Миграция завершена: {migration_result['migrated']} аккаунтов")
        elif migration_result['status'] == 'error':
            print(f"Ошибка миграции: {migration_result['message']}")
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
    
    # Start subscriber background task
    asyncio.create_task(process_subscription_queue())
    print("Фоновая задача подписчика запущена")
    
    # Только загрузить config.json - БЕЗ подключения к Telegram
    if os.path.exists('config.json'):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if 'telegram' in config_data:
                telegram_config.update(config_data['telegram'])\n                print("Конфигурация загружена из config.json")
        except Exception as e:
            print(f"Ошибка загрузки config.json: {e}")
    
    print("Приложение готово к работе")'''

content = content.replace(old_startup, new_startup)

# 4. Add subscriber endpoints before "if __name__ == "__main__":"
endpoints = '''

# ============================================
# SUBSCRIBER MODULE API ENDPOINTS
# ============================================

@app.post("/api/subscriber/add-tasks")
async def add_subscription_tasks(request: ChannelListRequest):
    """Add channels to subscription queue"""
    try:
        result = await add_channels_to_queue(request.channel_urls)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        
        return result
        
    except Exception as e:
        print(f"Error adding subscription tasks: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/subscriber/stats")
async def get_subscriber_stats():
    """Get subscription statistics"""
    try:
        stats = await get_subscription_stats()
        return stats
        
    except Exception as e:
        print(f"Error getting subscriber stats: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings/limits")
async def get_limits_settings():
    """Get current subscription limits"""
    try:
        max_subs = await get_setting("max_subs_per_day", 20)
        delay_min = await get_setting("delay_min_seconds", 30)
        delay_max = await get_setting("delay_max_seconds", 120)
        
        return {
            "max_subs_per_day": max_subs,
            "delay_min_seconds": delay_min,
            "delay_max_seconds": delay_max
        }
        
    except Exception as e:
        print(f"Error getting limits: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/limits")
async def update_limits_settings(settings: LimitsSettings):
    """Update subscription limits"""
    try:
        await set_setting("max_subs_per_day", settings.max_subs_per_day)
        await set_setting("delay_min_seconds", settings.delay_min_seconds)
        await set_setting("delay_max_seconds", settings.delay_max_seconds)
        
        return {"status": "success", "message": "Limits updated"}
        
    except Exception as e:
        print(f"Error updating limits: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

'''

content = content.replace(
    '\nif __name__ == "__main__":',
    f'{endpoints}\nif __name__ == "__main__":'
)

# Write the modified content
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("main.py successfully updated!")
