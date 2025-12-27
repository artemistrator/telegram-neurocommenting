import asyncio
import os
import zipfile
import shutil
from telethon import TelegramClient
from telethon.sessions import StringSession
from backend.directus_client import directus
from backend.services.account_import_service import import_accounts_from_zip

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

        # 2. Скачиваем файл
        await directus.download_file(file_uuid, zip_path)
        
        # 3. Читаем байты архива
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        # 4. Вызываем единый сервис импорта
        results = await import_accounts_from_zip(
            zip_bytes=zip_bytes,
            filename=f"{import_id}.zip",
            auto_assign_proxy=True,
            keep_session_file=False, # По умолчанию выключено
            user_created=import_item.get('user_created')
        )

        # 5. Формируем лог
        log_messages = []
        if results["status"] == "success":
            log_messages.append(f"✅ Imported {results['imported']} account(s).")
            for acc in results["accounts"]:
                proxy_str = " (with proxy)" if acc["proxy_assigned"] else ""
                log_messages.append(f"  - {acc['phone']}{proxy_str}")
        else:
            log_messages.append(f"❌ Import failed: {results.get('detail', 'Unknown error')}")

        if results["errors"]:
            log_messages.append("\n⚠️ Errors/Skipped:")
            for err in results["errors"]:
                log_messages.append(f"  - {err.get('phone') or err.get('file')}: {err['error_code']} ({err['detail']})")

        final_log = "\n".join(log_messages)
        await directus.update_item("imports", import_id, {
            "status": "completed" if results["status"] == "success" else "error",
            "log": final_log
        })
        print(f"✅ Import #{import_id} finished!")

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
            response = await directus.safe_get(
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

