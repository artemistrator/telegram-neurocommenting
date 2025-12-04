import asyncio
import os
import zipfile
import shutil
from telethon import TelegramClient
from telethon.sessions import StringSession
from backend.directus_client import directus

# Временная папка для распаковки
TEMP_DIR = "temp_imports"

# Дефолтные API credentials
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

async def process_import(import_item):
    import_id = import_item['id']
    file_uuid = import_item['archive_file']
    
    print(f"📦 Processing import #{import_id}...")
    
    # 1. Ставим статус 'processing'
    await directus.update_item("imports", import_id, {
        "status": "processing",
        "log": "Started processing..."
    })

    try:
        # Создаем временную папку
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
            
        zip_path = os.path.join(TEMP_DIR, f"{import_id}.zip")
        extract_path = os.path.join(TEMP_DIR, f"{import_id}_extracted")

        # 2. Скачиваем файл
        await directus.download_file(file_uuid, zip_path)
        
        # 3. Распаковываем
        log_messages = []
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        # 4. Ищем пары: .session + .json (опционально)
        session_data = {}  # {basename: {"session": path, "json": path}}
        
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                full_path = os.path.join(root, file)
                basename = os.path.splitext(file)[0]  # Имя без расширения
                
                if file.endswith(".session"):
                    if basename not in session_data:
                        session_data[basename] = {}
                    session_data[basename]["session"] = full_path
                    
                elif file.endswith(".json"):
                    if basename not in session_data:
                        session_data[basename] = {}
                    session_data[basename]["json"] = full_path
        
        log_messages.append(f"✅ Found {len(session_data)} session file(s).")
        
        # 5. Обрабатываем каждую сессию
        alive_count = 0
        dead_count = 0
        first_account = True  # Первый аккаунт станет слушателем
        
        for basename, paths in session_data.items():
            session_path = paths.get("session")
            json_path = paths.get("json")
            
            if not session_path:
                log_messages.append(f"⚠️ Skipping {basename}: no .session file")
                continue
            
            client = None
            try:
                log_messages.append(f"🔍 Checking {basename}...")
                
                # Читаем device_info из JSON (если есть)
                device_info = None
                if json_path and os.path.exists(json_path):
                    import json
                    with open(json_path, 'r', encoding='utf-8') as f:
                        device_info = json.load(f)
                
                # Создаем клиент из файла сессии
                client = TelegramClient(
                    session_path.replace(".session", ""),
                    DEFAULT_API_ID,
                    DEFAULT_API_HASH
                )
                
                await client.connect()
                
                # Проверяем валидность
                me = await client.get_me()
                
                if me:
                    # Аккаунт жив! Получаем данные
                    phone = me.phone if me.phone else basename
                    session_string = StringSession.save(client.session)
                    
                    # Определяем work_mode
                    work_mode = "listener" if first_account else "reserve"
                    first_account = False  # Следующие будут резервными
                    
                    # Сохраняем в Directus со всеми полями
                    account_data = {
                        "phone": phone,
                        "session_string": session_string,
                        "api_id": DEFAULT_API_ID,
                        "api_hash": DEFAULT_API_HASH,
                        "work_mode": work_mode,
                        "status": "active",
                        "is_converted": True,
                        "user_created": import_item.get('user_created')
                    }
                    
                    # Добавляем device_info, если есть JSON
                    if device_info:
                        account_data["device_info"] = device_info
                    
                    # Создаём аккаунт в Directus
                    created_account = await directus.create_item("accounts", account_data)
                    account_id = created_account.get('id')
                    
                    # 🔗 Пытаемся привязать прокси
                    proxy_info = ""
                    try:
                        user_id = import_item.get('user_created')
                        available_proxy = await directus.get_available_proxy(user_id)
                        
                        if available_proxy:
                            proxy_id = available_proxy['id']
                            proxy_host = available_proxy['host']
                            proxy_port = available_proxy['port']
                            
                            # Обновляем аккаунт - привязываем прокси
                            await directus.update_item("accounts", account_id, {
                                "proxy_id": proxy_id
                            })
                            
                            # Обновляем прокси - привязываем к аккаунту
                            await directus.update_item("proxies", proxy_id, {
                                "assigned_to": account_id
                            })
                            
                            proxy_info = f" → proxy {proxy_host}:{proxy_port}"
                            log_messages.append(f"✅ {basename} ({phone}) - {work_mode}{proxy_info}")
                        else:
                            proxy_info = " → no proxy available"
                            log_messages.append(f"⚠️ {basename} ({phone}) - {work_mode}{proxy_info}")
                            
                    except Exception as proxy_error:
                        # Если не удалось привязать прокси - не фейлим весь импорт
                        print(f"⚠️ Proxy assignment failed for {basename}: {proxy_error}")
                        log_messages.append(f"⚠️ {basename} ({phone}) - {work_mode} → proxy assignment failed")
                    
                    alive_count += 1
                else:
                    log_messages.append(f"💀 {basename} - Dead account")
                    dead_count += 1
                    
            except Exception as e:
                log_messages.append(f"❌ {basename} - Error: {str(e)}")
                dead_count += 1
                
            finally:
                # Всегда закрываем клиент
                if client:
                    await client.disconnect()
        
        # 6. Финал - Успех
        log_messages.append(f"\n📊 Summary: {alive_count} alive, {dead_count} dead/error")
        final_log = "\n".join(log_messages)
        await directus.update_item("imports", import_id, {
            "status": "completed",
            "log": final_log
        })
        print(f"✅ Import #{import_id} completed!")

    except Exception as e:
        print(f"❌ Error processing #{import_id}: {e}")
        await directus.update_item("imports", import_id, {
            "status": "error",
            "log": f"Error: {str(e)}"
        })
    finally:
        # Чистим мусор
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)


async def run_worker():
    print("👀 Import Worker started.")
    
    # 1. Сначала логинимся!
    print("🔑 Logging in...")
    try:
        await directus.login()
        print("✅ Logged in successfully.")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return

    print("Waiting for tasks...")
    
    while True:
        try:
            # 2. Используем клиент для запроса
            # ВАЖНО: client.get возвращает объект Response, нужно вызвать .json()
            response = await directus.client.get(
                "/items/imports", 
                params={"filter[status][_eq]": "uploaded"}
            )
            
            # Если токен протух (401), пробуем перелогиниться
            if response.status_code == 401:
                print("🔄 Token expired, refreshing...")
                await directus.login()
                continue
                
            # Если другая ошибка - выбрасываем её
            response.raise_for_status()
            
            # Получаем данные
            data = response.json()
            items = data.get('data', []) # Используем .get на случай, если ключа нет
            
            if items:
                for item in items:
                    await process_import(item)
            
        except Exception as e:
            print(f"⚠️ Worker Loop Error: {e}")
            # Добавим подробностей для отладки, если ошибка останется
            import traceback
            traceback.print_exc()
            
        await asyncio.sleep(5) # Отдыхаем 5 секунд
if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped manually")

