import asyncio
import json
import os
import traceback
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
import aiohttp
import sys
from datetime import datetime, timedelta
from account_manager import AccountManager
from database import init_database, migrate_from_json, get_setting, set_setting
from subscriber import add_channels_to_queue, process_subscription_queue, get_subscription_stats
from backend.routers import dashboard
from backend.directus_client import DirectusClient
from database import init_database, migrate_from_json, get_setting, set_setting
from subscriber import add_channels_to_queue, process_subscription_queue, get_subscription_stats



# Configuration file
CONFIG_FILE = 'config.json'

# Global variables
telegram_client: Optional[TelegramClient] = None
telegram_config = {
    "api_id": None,
    "api_hash": None,
    "phone": None,
    "session": "telegram_session"
}
config: Dict = {}
monitor_process = None
monitoring_active = False
event_log: List[Dict] = []
account_mgr = AccountManager()

# Load config from file at startup
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        saved_config = json.load(f)
        telegram_config.update(saved_config.get('telegram', {}))
        config = saved_config
else:
    config = {}


def mask_string(s: str, visible_chars: int = 4) -> str:
    """Mask sensitive string showing only first 2 and last N chars"""
    if not s or len(str(s)) <= visible_chars:
        return s
    s_str = str(s)
    return s_str[:2] + "*" * (len(s_str) - visible_chars - 2) + s_str[-visible_chars:]

# Pydantic models
class TelegramConfig(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    session: str = "telegram_session"

class AuthCode(BaseModel):
    code: str

class AuthPassword(BaseModel):
    password: str

class WebhookConfig(BaseModel):
    url: str

class ChatSelection(BaseModel):
    chats: List[int]

class OpenAISettings(BaseModel):
    ai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-5-nano"
    system_prompt: str = (
        "Ты классификатор сообщений из чатов фрилансеров. Твоя задача — определить, "
        "содержит ли сообщение поиск исполнителя, вакансию или предложение работы. "
        "Если сообщение — это вопрос новичка, спам, реклама услуг или просто общение — "
        "возвращай false. Если это заказ/вакансия — возвращай true. Ответь ТОЛЬКО "
        "валидным JSON формата: {\"relevant\": true} или {\"relevant\": false}"
    )
    min_words: int = 5
    use_triggers: bool = True
    trigger_words: List[str] = []

class MonitoringSettings(BaseModel):
    min_words: int = 5
    use_triggers: bool = True
    trigger_words: List[str] = []

class ChannelListRequest(BaseModel):
    channel_urls: List[str]

class LimitsSettings(BaseModel):
    max_subs_per_day: int
    delay_min_seconds: int
    delay_max_seconds: int


# Save config to file
def save_config():
    # Update the telegram section in config
    config['telegram'] = telegram_config
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(dashboard.router)

# CORS middleware для доступа к Dashboard API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация Directus клиента для Dashboard API
directus_client = DirectusClient()

# Startup event
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
    
    # Подключение к Directus для Dashboard API
    try:
        await directus_client.login()
        print("✓ Directus подключен для Dashboard API")
    except Exception as e:
        print(f"⚠ Ошибка подключения к Directus: {e}")
    
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

# Get HTML page
@app.get("/", response_class=HTMLResponse)
async def get_layout():
    """Return layout with sidebar navigation"""
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/pages/{page}", response_class=HTMLResponse)
async def get_page(page: str):
    """Return individual page content"""
    try:
        page_path = os.path.join("pages", f"{page}.html")
        with open(page_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Page '{page}' not found")

# Telegram API endpoints
@app.post("/api/telegram/save")
async def save_telegram_config(data: dict):
    telegram_config["api_id"] = data.get("api_id")
    telegram_config["api_hash"] = data.get("api_hash")
    telegram_config["phone"] = data.get("phone")
    telegram_config["session"] = data.get("session", "telegram_session")
    
    if not telegram_config.get("api_id") or not telegram_config.get("api_hash"):
        raise HTTPException(status_code=400, detail="Сначала сохраните настройки Telegram через кнопку 'Сохранить настройки'")
    
    if not telegram_config.get("phone"):
        raise HTTPException(status_code=400, detail="Укажите номер телефона")
    
    try:
        # Создать клиент
        global telegram_client
        telegram_client = TelegramClient(
            telegram_config["session"],
            int(telegram_config["api_id"]) if isinstance(telegram_config["api_id"], str) else telegram_config["api_id"],
            telegram_config["api_hash"]
        )
        
        # Подключиться
        await telegram_client.connect()
        
        # Отправить код
        await telegram_client.send_code_request(telegram_config["phone"])
        
        return {"status": "success", "message": "Код отправлен в Telegram"}
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка авторизации: {str(e)}")

@app.post("/api/telegram/auth/start")
async def start_telegram_auth():
    global telegram_client
    
    if not telegram_config.get("phone"):
        raise HTTPException(status_code=400, detail="Phone number not set")
    
    try:
        if not telegram_client:
            telegram_client = TelegramClient(
                telegram_config['session'],
                int(telegram_config['api_id']),
                telegram_config['api_hash']
            )
        
        if not telegram_client.is_connected():
            await telegram_client.connect()
            
        if not await telegram_client.is_user_authorized():
            await telegram_client.send_code_request(telegram_config["phone"])
            return {"status": "success", "message": "Code sent"}
        else:
            return {"status": "success", "message": "Already authorized"}
            
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/telegram/auth/code")
async def submit_auth_code(auth_code: AuthCode):
    global telegram_client
    
    if not telegram_client:
        raise HTTPException(status_code=400, detail="Authentication not started")
    
    try:
        await telegram_client.sign_in(telegram_config["phone"], auth_code.code)
    except SessionPasswordNeededError:
        return {"status": "need_2fa"}
    except Exception as e:
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))
    
    # Get user info
    me = await telegram_client.get_me()
    # Convert user object to dict safely
    user_dict = me.to_dict() if hasattr(me, 'to_dict') else {}
    user_data = {
        "id": user_dict.get('id', ''),
        "first_name": user_dict.get('first_name', ''),
        "last_name": user_dict.get('last_name', ''),
        "username": user_dict.get('username', '')
    }
    return {
        "status": "success",
        "user": user_data
    }

@app.post("/api/telegram/auth/password")
async def submit_auth_password(auth_password: AuthPassword):
    global telegram_client
    
    if not telegram_client:
        raise HTTPException(status_code=400, detail="Authentication not started")
    
    try:
        await telegram_client.sign_in(password=auth_password.password)
    except Exception as e:
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))
    
    # Get user info
    me = await telegram_client.get_me()
    # Convert user object to dict safely
    user_dict = me.to_dict() if hasattr(me, 'to_dict') else {}
    user_data = {
        "id": user_dict.get('id', ''),
        "first_name": user_dict.get('first_name', ''),
        "last_name": user_dict.get('last_name', ''),
        "username": user_dict.get('username', '')
    }
    return {
        "status": "success",
        "user": user_data
    }

@app.get("/api/telegram/status")
async def get_telegram_status():
    global telegram_client
    
    # 1. Если клиент уже в памяти и авторизован
    if telegram_client:
        if await telegram_client.is_user_authorized():
            return {"authorized": True}

    # 2. Если клиента нет, но есть файл сессии на диске — пробуем восстановить
    session_name = telegram_config.get("session", "telegram_session")
    session_file = f"{session_name}.session"
    if os.path.exists(session_file):
        try:
            if not telegram_client:
                 telegram_client = TelegramClient(
                    session_name,
                    int(telegram_config['api_id']),
                    telegram_config['api_hash']
                )
            
            if not telegram_client.is_connected():
                await telegram_client.connect()
            
            if await telegram_client.is_user_authorized():
                return {"authorized": True}
        except Exception as e:
            print(f"Error restoring session: {e}")
            
    return {"authorized": False}

@app.get("/api/chats/list")
async def get_chats():
    global telegram_client
    
    # Проверить настройки
    if not telegram_config.get("api_id"):
        raise HTTPException(status_code=401, detail="Сначала сохраните настройки и авторизуйтесь")
    
    # Если клиента нет или он не подключен - создать новый
    if not telegram_client:
        try:
            telegram_client = TelegramClient(
                telegram_config['session'],
                int(telegram_config['api_id']) if isinstance(telegram_config['api_id'], str) else telegram_config['api_id'],
                telegram_config['api_hash']
            )
            await telegram_client.connect()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка подключения: {e}")
    
    # Проверить авторизацию
    if not await telegram_client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Сначала авторизуйтесь")
    
    # Получить чаты
    try:
        chats = []
        async for dialog in telegram_client.iter_dialogs():
            chat_type = 'Канал' if dialog.is_channel else 'Группа' if dialog.is_group else 'Личка'
            chats.append({
                'id': dialog.id,
                'name': dialog.name,
                'type': chat_type
            })
        
        return {"chats": chats}
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chats/save")
async def save_chats(chat_selection: ChatSelection):
    # Создать список объектов с ID чатов для monitor.py
    config['monitored_chats'] = [{'id': chat_id} for chat_id in chat_selection.chats]
    save_config()
    return {"status": "success"}

# Webhook API endpoints
@app.post("/api/webhook/save")
async def save_webhook(webhook: WebhookConfig):
    config['webhook_url'] = webhook.url
    save_config()
    return {"status": "success"}


@app.post("/api/webhook/test")
async def test_webhook():
    if not config.get('webhook_url'):
        raise HTTPException(status_code=400, detail="Webhook URL not configured")
    
    test_data = {
        "test": True,
        "message": "Test message from Telegram Monitor",
        "timestamp": "now"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(config['webhook_url'], json=test_data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return {"status": "success", "message": "Test message sent successfully"}
                else:
                    raise HTTPException(status_code=500, detail=f"N8N returned {resp.status}")
        except Exception as e:
            print(f"ERROR: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error sending test message: {str(e)}")

# OpenAI API endpoints
@app.post("/api/openai/save")
async def save_openai_settings(settings: OpenAISettings):
    """Save OpenAI settings to config"""
    # Update config with OpenAI settings
    config['openai'] = settings.dict()
    save_config()
    
    return {"status": "success"}

@app.get("/api/openai/status")
async def get_openai_status():
    """Get current OpenAI settings"""
    # Return current OpenAI settings or defaults
    openai_settings = config.get('openai', {})
    
    return {
        "ai_enabled": openai_settings.get('ai_enabled', False),
        "openai_api_key": openai_settings.get('openai_api_key', ''),
        "openai_model": openai_settings.get('openai_model', 'gpt-5-nano'),
        "system_prompt": openai_settings.get('system_prompt', 'Ты классификатор сообщений из чатов фрилансеров. Твоя задача — определить, содержит ли сообщение поиск исполнителя, вакансию или предложение работы. Если сообщение — это вопрос новичка, спам, реклама услуг или просто общение — возвращай false. Если это заказ/вакансия — возвращай true. Ответь ТОЛЬКО валидным JSON формата: {"relevant": true} или {"relevant": false}'),
        "min_words": openai_settings.get('min_words', 5),
        "use_triggers": openai_settings.get('use_triggers', True),
        "trigger_words": openai_settings.get('trigger_words', ['ищу', 'нужен', 'требуется', 'заказ', 'сделать', 'настроить', 'разработать', 'кто может', 'помогите'])
    }

# Monitoring functions

async def read_monitor_output():
    """Читать stdout и stderr monitor.py и логировать"""
    global monitor_process

    if not monitor_process:
        return

    try:
        # Читаем stdout и stderr параллельно
        async def read_stream(stream, prefix):
            if not stream:
                return
            try:
                async for line in stream:
                    # Декодируем с игнорированием ошибок для предотвращения UnicodeDecodeError
                    decoded = line.decode('utf-8', errors='replace').strip()
                    if decoded:
                        print(f"[MONITOR {prefix}] {decoded}", flush=True)
            except Exception as e:
                print(f"[MONITOR {prefix}] Error reading stream: {e}", flush=True)

        await asyncio.gather(
            read_stream(monitor_process.stdout, "OUT"),
            read_stream(monitor_process.stderr, "ERR"),
        )

    except Exception as e:
        print(f"Error reading monitor output: {e}")
        print(traceback.format_exc())


@app.post("/api/monitor/start")
async def start_monitoring():
    global monitor_process, monitoring_active
    
    if monitoring_active:
        return {"status": "already_running"}
    
    # Проверить конфигурацию
    if not config.get('monitored_chats'):
        raise HTTPException(400, "Выберите чаты для мониторинга")
    
    # Use trigger words from OpenAI settings instead of old keywords
    # Add default values for OpenAI settings
    openai_settings = config.get('openai', {
        'ai_enabled': False,
        'use_triggers': True,
        'trigger_words': ['ищу', 'нужен', 'требуется', 'заказ', 'сделать', 'настроить', 'разработать', 'кто может', 'помогите']
    })
    trigger_words = openai_settings.get('trigger_words', [])
    
    # Проверка зависит от настроек AI
    ai_enabled = openai_settings.get('ai_enabled', False)
    use_triggers = openai_settings.get('use_triggers', True)
    
    # Если триггеры включены, но список пустой — это ошибка
    if use_triggers and not trigger_words:
        raise HTTPException(400, "Добавьте триггерные слова в настройках AI")
    
    # Если AI выключен и триггеры выключены — это тоже ошибка (нечего мониторить)
    if not ai_enabled and not use_triggers:
        raise HTTPException(400, "Включите AI-фильтр или триггерные слова")
        
    if not config.get('webhook_url'):
        raise HTTPException(400, "Укажите webhook URL")
    
    try:
        print("Запуск мониторинга через monitor.py...")
        
        # Disconnect main process client to release database lock
        if telegram_client and telegram_client.is_connected():
            print("Отключение основного клиента для освобождения БД...", flush=True)
            await telegram_client.disconnect()
        
        # Создать окружение с правильной кодировкой и отключенным буфером
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        
        # Запустить monitor.py как отдельный процесс
        monitor_process = await asyncio.create_subprocess_exec(
            sys.executable, 'monitor.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        monitoring_active = True
        
        # Читать вывод в фоне
        asyncio.create_task(read_monitor_output())
        
        return {"status": "started"}
        
    except Exception as e:
        print(f"ERROR starting monitor: {e}")
        print(traceback.format_exc())
        raise HTTPException(500, str(e))

@app.post("/api/monitor/stop")
async def stop_monitoring():
    global monitor_process, monitoring_active
    
    if monitor_process:
        try:
            monitor_process.terminate()
            # Wait for the process to terminate with a timeout
            try:
                await asyncio.wait_for(monitor_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # If it doesn't terminate gracefully, kill it
                monitor_process.kill()
                await monitor_process.wait()
        except ProcessLookupError:
            # Process already terminated
            pass
        monitor_process = None
    
    monitoring_active = False
    return {"status": "stopped"}

@app.post("/api/monitor/event")
async def push_monitor_event(event: dict):
    # event: {time, chat_name, keywords, text_preview}
    global event_log
    event_log.append(event)
    # хранить только последние 20 событий
    if len(event_log) > 20:
        event_log.pop(0)
    return {"status": "ok"}

@app.get("/api/monitor/status")
async def get_monitor_status():
    global event_log
    
    # Use trigger words from OpenAI settings instead of old keywords
    openai_settings = config.get('openai', {})
    trigger_words = openai_settings.get('trigger_words', [])
    
    return {
        "active": monitoring_active,
        "chats_count": len(config.get('monitored_chats', [])),
        "keywords_count": len(trigger_words),
        "events": event_log
    }

@app.get("/api/monitor/logs")
async def stream_logs():
    async def event_generator():
        last_count = len(event_log)
        while True:
            await asyncio.sleep(1)
            if len(event_log) != last_count:
                last_count = len(event_log)
                # Send the latest event
                if event_log:
                    yield f"data: {json.dumps(event_log[-1])}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/config/get")
async def get_current_config():
    """Return safe config for UI display"""
    safe_config = {
        "telegram": {
            "api_id": mask_string(str(telegram_config.get("api_id", "")), 3) if telegram_config.get("api_id") else "",
            "api_hash": mask_string(telegram_config.get("api_hash", ""), 4) if telegram_config.get("api_hash") else "",
            "phone": mask_string(telegram_config.get("phone", ""), 4) if telegram_config.get("phone") else "",
            "session": telegram_config.get("session", "telegram_session"),
            "is_configured": bool(telegram_config.get("api_id") and telegram_config.get("api_hash"))
        },
        "webhook_url": mask_string(config.get("webhook_url", ""), 8) if config.get("webhook_url") else "",
        "monitored_chats": [{"id": chat["id"], "name": "Chat"} for chat in config.get("monitored_chats", [])],
        "monitored_chats_count": len(config.get("monitored_chats", []))
    }
    return safe_config


@app.post("/api/telegram/logout")
async def logout_telegram():
    """Logout from Telegram and delete session file"""
    global telegram_client
    
    try:
        if telegram_client:
            await telegram_client.log_out()
            await telegram_client.disconnect()
            telegram_client = None
        
        return {"status": "success", "message": "Сессия сброшена"}
    except Exception as e:
        raise HTTPException(500, f"Ошибка выхода: {str(e)}")

# ============================================
# ACCOUNT MANAGEMENT API ENDPOINTS
# ============================================

@app.post("/api/accounts/import-csv")
async def import_accounts_csv(
    csv_file: UploadFile = File(...),
    session_files: List[UploadFile] = File(...)
):
    """Import accounts from CSV and session files"""
    try:
        # Read CSV content
        csv_content = (await csv_file.read()).decode('utf-8')
        
        # Read session files
        session_file_dict = {}
        for session_file in session_files:
            content = await session_file.read()
            session_file_dict[session_file.filename] = content
        
        # Import accounts
        result = await account_mgr.import_from_csv(csv_content, session_file_dict)
        
        return {
            "status": "success",
            "imported": result['imported'],
            "errors": result['errors'],
            "total": result['total']
        }
        
    except Exception as e:
        print(f"Error importing accounts: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/auth/start")
async def start_account_auth(data: dict):
    """Start account authorization - send code to Telegram"""
    try:
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        phone = data.get('phone')
        proxy = data.get('proxy')
        
        if not all([api_id, api_hash, phone]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        result = await account_mgr.start_auth(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            proxy=proxy
        )
        
        if result['status'] == 'flood_wait':
            raise HTTPException(
                status_code=429,
                detail=f"Telegram ограничил запросы. Подождите {result['wait_seconds']} секунд"
            )
        
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error starting auth: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/auth/code")
async def submit_auth_code(data: dict):
    """Submit SMS code for account authorization"""
    try:
        account_id = data.get('account_id')
        code = data.get('code')
        
        if not all([account_id, code]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        result = await account_mgr.submit_code(int(account_id), code)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error submitting code: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/auth/password")
async def submit_auth_password(data: dict):
    """Submit 2FA password for account authorization"""
    try:
        account_id = data.get('account_id')
        password = data.get('password')
        
        if not all([account_id, password]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        result = await account_mgr.submit_password(int(account_id), password)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error submitting password: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/test-proxy")
async def test_proxy_connection(data: dict):
    """Test proxy connection to Telegram"""
    try:
        proxy_config = {
            'type': data.get('type', 'socks5'),
            'host': data.get('host'),
            'port': data.get('port'),
            'username': data.get('username', ''),
            'password': data.get('password', '')
        }
        
        if not all([proxy_config['host'], proxy_config['port']]):
            raise HTTPException(status_code=400, detail="Missing proxy host or port")
        
        result = await account_mgr.test_proxy(proxy_config)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error testing proxy: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/accounts/list")
async def get_accounts_list():
    """Get list of accounts with masked sensitive data"""
    try:
        accounts = await account_mgr.get_accounts_list(mask_sensitive=True)
        return {"accounts": accounts}
        
    except Exception as e:
        print(f"Error getting accounts: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    """Delete account and its session file"""
    try:
        success = await account_mgr.delete_account(account_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {"status": "success", "message": "Account deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting account: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# END ACCOUNT MANAGEMENT API
# ============================================




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



# ============================================
# DASHBOARD API ENDPOINTS
# ============================================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(user_id: Optional[str] = Query(None)):
    """
    Получить общую статистику комментариев
    
    Возвращает:
    - total_comments: общее количество комментов
    - posted: успешно отправленные
    - failed: с ошибками
    - pending: в очереди
    - today_comments: комментов за сегодня
    - success_rate: процент успешных
    """
    try:
        print(f"[Dashboard API] Запрос статистики (user_id={user_id})")
        
        # Параметры запроса с фильтрацией по пользователю
        params = {
            "fields": "id,status,posted_at",
            "limit": -1  # Получить все записи
        }
        
        if user_id:
            params["filter[user_created][_eq]"] = user_id
        
        # Получить все записи из comment_queue
        response = await directus_client.client.get("/items/comment_queue", params=params)
        comments = response.json().get('data', [])
        
        print(f"[Dashboard API] Получено {len(comments)} записей из comment_queue")
        
        # Подсчёт статистики
        total_comments = len(comments)
        posted = sum(1 for c in comments if c.get('status') == 'posted')
        failed = sum(1 for c in comments if c.get('status') == 'failed')
        pending = sum(1 for c in comments if c.get('status') == 'pending')
        
        # Комментарии за сегодня
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_comments = sum(
            1 for c in comments 
            if c.get('posted_at') and datetime.fromisoformat(c['posted_at'].replace('Z', '+00:00')) >= today_start
        )
        
        # Процент успешных
        success_rate = round((posted / total_comments * 100), 2) if total_comments > 0 else 0
        
        result = {
            "total_comments": total_comments,
            "posted": posted,
            "failed": failed,
            "pending": pending,
            "today_comments": today_comments,
            "success_rate": success_rate
        }
        
        print(f"[Dashboard API] Статистика: {result}")
        return result
        
    except Exception as e:
        print(f"[Dashboard API] Ошибка получения статистики: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/activity")
async def get_dashboard_activity(
    days: int = Query(7, ge=1, le=90),
    user_id: Optional[str] = Query(None)
):
    """
    Получить график активности комментирования по дням
    
    Параметры:
    - days: количество дней для отображения (по умолчанию 7)
    - user_id: фильтр по пользователю (опционально)
    
    Возвращает:
    - labels: массив дат в формате YYYY-MM-DD
    - data: массив количества комментов за каждый день
    """
    try:
        print(f"[Dashboard API] Запрос активности за {days} дней (user_id={user_id})")
        
        # Вычислить диапазон дат
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = end_date - timedelta(days=days - 1)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Параметры запроса
        params = {
            "fields": "posted_at",
            "filter[status][_eq]": "posted",
            "filter[posted_at][_gte]": start_date.isoformat(),
            "limit": -1
        }
        
        if user_id:
            params["filter[user_created][_eq]"] = user_id
        
        # Получить комментарии за период
        response = await directus_client.client.get("/items/comment_queue", params=params)
        comments = response.json().get('data', [])
        
        print(f"[Dashboard API] Получено {len(comments)} комментов за период")
        
        # Группировка по датам
        date_counts = {}
        for comment in comments:
            if comment.get('posted_at'):
                posted_date = datetime.fromisoformat(comment['posted_at'].replace('Z', '+00:00')).date()
                date_str = posted_date.strftime('%Y-%m-%d')
                date_counts[date_str] = date_counts.get(date_str, 0) + 1
        
        # Создать массивы labels и data для всех дней (заполнить пропуски нулями)
        labels = []
        data = []
        
        current_date = start_date.date()
        for i in range(days):
            date_str = current_date.strftime('%Y-%m-%d')
            labels.append(date_str)
            data.append(date_counts.get(date_str, 0))
            current_date += timedelta(days=1)
        
        result = {
            "labels": labels,
            "data": data
        }
        
        print(f"[Dashboard API] График активности: {len(labels)} дней, всего {sum(data)} комментов")
        return result
        
    except Exception as e:
        print(f"[Dashboard API] Ошибка получения активности: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/top-channels")
async def get_top_channels(
    limit: int = Query(10, ge=1, le=50),
    user_id: Optional[str] = Query(None)
):
    """
    Получить топ каналов по количеству комментариев
    
    Параметры:
    - limit: количество каналов для отображения (по умолчанию 10)
    - user_id: фильтр по пользователю (опционально)
    
    Возвращает:
    - channels: массив объектов {channel_url, count}
    """
    try:
        print(f"[Dashboard API] Запрос топ-{limit} каналов (user_id={user_id})")
        
        # Параметры запроса
        params = {
            "fields": "channel_url",
            "limit": -1
        }
        
        if user_id:
            params["filter[user_created][_eq]"] = user_id
        
        # Получить все комментарии
        response = await directus_client.client.get("/items/comment_queue", params=params)
        comments = response.json().get('data', [])
        
        print(f"[Dashboard API] Получено {len(comments)} комментов для группировки")
        
        # Группировка по каналам
        channel_counts = {}
        for comment in comments:
            channel_url = comment.get('channel_url', 'Unknown')
            channel_counts[channel_url] = channel_counts.get(channel_url, 0) + 1
        
        # Сортировка по количеству (DESC) и ограничение
        sorted_channels = sorted(
            channel_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        # Формирование результата
        channels = [
            {"channel_url": url, "count": count}
            for url, count in sorted_channels
        ]
        
        result = {"channels": channels}
        
        print(f"[Dashboard API] Топ каналов: {len(channels)} записей")
        return result
        
    except Exception as e:
        print(f"[Dashboard API] Ошибка получения топ каналов: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/recent-comments")
async def get_recent_comments(
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None)
):
    """
    Получить последние комментарии с деталями
    
    Параметры:
    - limit: количество комментариев для отображения (по умолчанию 20)
    - user_id: фильтр по пользователю (опционально)
    
    Возвращает:
    - comments: массив объектов с полями:
      - id, status, channel_url
      - generated_comment (обрезан до 100 символов)
      - posted_at, error_message
      - account_phone (из связанного аккаунта)
    """
    try:
        print(f"[Dashboard API] Запрос последних {limit} комментов (user_id={user_id})")
        
        # Параметры запроса с JOIN к accounts через field expansion
        params = {
            "fields": "*,account_id.phone",
            "sort": "-id",  # Сортировка по ID DESC (новые первыми)
            "limit": limit
        }
        
        if user_id:
            params["filter[user_created][_eq]"] = user_id
        
        # Получить комментарии с данными аккаунтов
        response = await directus_client.client.get("/items/comment_queue", params=params)
        comments_data = response.json().get('data', [])
        
        print(f"[Dashboard API] Получено {len(comments_data)} последних комментов")
        
        # Форматирование результата
        comments = []
        for comment in comments_data:
            # Обрезать текст комментария до 100 символов
            generated_comment = comment.get('generated_comment') or ''
            if len(generated_comment) > 100:
                generated_comment = generated_comment[:100] + '...'
            
            # Получить phone из вложенного объекта account_id
            account_phone = None
            if isinstance(comment.get('account_id'), dict):
                account_phone = comment['account_id'].get('phone')
            
            comments.append({
                "id": comment.get('id'),
                "status": comment.get('status'),
                "channel_url": comment.get('channel_url'),
                "generated_comment": generated_comment,
                "posted_at": comment.get('posted_at'),
                "error_message": comment.get('error_message'),
                "account_phone": account_phone
            })
        
        result = {"comments": comments}
        
        print(f"[Dashboard API] Последние комментарии: {len(comments)} записей")
        return result
        
    except Exception as e:
        print(f"[Dashboard API] Ошибка получения последних комментов: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# END DASHBOARD API
# ============================================


# ============================================
# SPA ROUTING - Catch-all for page refreshes
# ============================================

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    """Catch-all route for SPA routing - returns layout.html for all non-API/static paths"""
    # Ignore API and static paths
    if full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("pages"):
        raise HTTPException(status_code=404)
    
    # All other paths (home, accounts, subscriber, etc.) return layout
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)