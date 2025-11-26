# INTEGRATION GUIDE: Subscriber Module

## Что уже сделано:

1. ✅ **database.py** - Полностью готов
   - Модели: Account, SubscriptionTask, GlobalSettings
   - Инициализация БД и миграция из JSON
   - Функции get_setting/set_setting

2. ✅ **subscriber.py** - Полностью готов
   - add_channels_to_queue() - распределение с load balancing
   - process_subscription_queue() - фоновая обработка
   - get_subscription_stats() - статистика
   - Проверка лимитов и задержки

3. ✅ **account_manager.py** - Полностью переписан на БД
   - Все методы теперь работают с SQLModel
   - Сохранена обратная совместимость API

4. ✅ **requirements.txt** - Обновлен
   - Добавлены: sqlmodel, aiosqlite, python-multipart

5. ✅ **subscriber_endpoints.txt** - Готовые endpoint'ы для main.py

## Что нужно сделать вручную:

### 1. Обновить main.py

#### A. Добавить импорты (в начало файла, после строки 14):
```python
from database import init_database, migrate_from_json, get_setting, set_setting
from subscriber import add_channels_to_queue, process_subscription_queue, get_subscription_stats
```

#### B. Добавить Pydantic модели (после существующих моделей, ~строка 88):
```python
class ChannelListRequest(BaseModel):
    channel_urls: List[str]

class LimitsSettings(BaseModel):
    max_subs_per_day: int
    delay_min_seconds: int
    delay_max_seconds: int
```

#### C. Обновить startup_event (заменить функцию на ~строке 101):
```python
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
                telegram_config.update(config_data['telegram'])
                print("Конфигурация загружена из config.json")
        except Exception as e:
            print(f"Ошибка загрузки config.json: {e}")
    
    print("Приложение готово к работе")
```

#### D. Добавить Subscriber API endpoints (в конец файла, перед `if __name__ == "__main__":`):

Скопировать весь код из файла `subscriber_endpoints.txt`.

### 2. Создать UI страницу

Создать файл `pages/subscriber.html` - я создам его в следующем шаге.

### 3. Обновить layout.html

Добавить ссылку на страницу Subscriber в навигацию (sidebar).

## Тестирование:

1. Запустить приложение:
   ```bash
   python main.py
   ```

2. Проверить в консоли:
   - "База данных инициализирована"
   - "Миграция завершена: X аккаунтов" (если были аккаунты в JSON)
   - "Фоновая задача подписчика запущена"

3. Проверить создание файла `app.db`

4. Если были аккаунты в `accounts.json`, проверить создание `accounts.json.bak`

## API Endpoints (после интеграции):

- `POST /api/subscriber/add-tasks` - добавить каналы в очередь
- `GET /api/subscriber/stats` - получить статистику
- `GET /api/settings/limits` - получить лимиты
- `POST /api/settings/limits` - обновить лимиты

## Примечания:

- AccountManager теперь работает полностью через БД
- Все существующие endpoint'ы для аккаунтов продолжат работать
- Миграция из JSON происходит автоматически при первом запуске
- Фоновая задача подписчика запускается автоматически и работает постоянно
