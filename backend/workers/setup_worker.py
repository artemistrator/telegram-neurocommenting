"""
Telegram Account Setup Worker

Автоматическая упаковка Telegram аккаунтов по стратегии "Double Layer":
Аккаунт -> Личный канал -> Целевая ссылка

Воркер берет "сырые" аккаунты (setup_status='pending') и превращает их в готовых ботов
с личными каналами-прокладками.
"""

import asyncio
import os
import sys
import random
import string
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UsernameOccupiedError,
    ChannelsAdminPublicTooMuchError,
    UsernameInvalidError
)
from telethon.sessions import StringSession
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditPhotoRequest,
    UpdateUsernameRequest
)
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.types import InputChatUploadedPhoto

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Directus client
directus = DirectusClient()

# Configuration
CHECK_INTERVAL = 60  # 60 секунд между циклами
TEMP_DIR = Path("temp_setup_files")  # Временная папка для файлов


async def get_pending_account() -> Optional[Dict]:
    """
    Получить один аккаунт для настройки.
    
    Критерии:
    - status='active'
    - setup_status='pending'
    
    Returns:
        Account dictionary или None
    """
    try:
        params = {
            "filter[status][_eq]": "active",
            "filter[setup_status][_eq]": "pending",
            "fields": "id,phone,session_string,api_id,api_hash,user_created,template_id",
            "limit": 1
        }
        
        response = await directus.client.get("/items/accounts", params=params)
        accounts = response.json().get('data', [])
        
        if accounts:
            account = accounts[0]
            logger.info(f"[Setup] Найден аккаунт для настройки: {account['phone']}")
            return account
        else:
            logger.info("[Setup] Нет аккаунтов для настройки")
            return None
            
    except Exception as e:
        logger.error(f"[Setup] Ошибка получения аккаунта: {e}")
        return None


async def get_template_by_id(template_id: int) -> Optional[Dict]:
    """
    Получить шаблон по ID.
    
    Args:
        template_id: ID шаблона
        
    Returns:
        Template dictionary или None
    """
    try:
        params = {
            "fields": "*"
        }
        
        response = await directus.client.get(f"/items/setup_templates/{template_id}", params=params)
        template = response.json().get('data')
        
        if template:
            logger.info(f"[Setup] Загружен шаблон: {template.get('name', 'Unknown')}")
            return template
        else:
            logger.error(f"[Setup] Шаблон с ID {template_id} не найден")
            return None
            
    except Exception as e:
        logger.error(f"[Setup] Ошибка получения шаблона {template_id}: {e}")
        return None


async def download_template_files(template: Dict) -> Dict[str, Optional[Path]]:
    """
    Скачать файлы из шаблона во временную папку.
    
    Args:
        template: Шаблон с file_id для аватарок
    
    Returns:
        Dict с путями к скачанным файлам
    """
    TEMP_DIR.mkdir(exist_ok=True)
    
    files = {
        "account_avatar": None,
        "channel_avatar": None
    }
    
    try:
        # Скачать account_avatar
        account_avatar_id = template.get('account_avatar')
        if account_avatar_id:
            account_avatar_path = TEMP_DIR / f"account_avatar_{template['id']}.jpg"
            await directus.download_file(account_avatar_id, str(account_avatar_path))
            files["account_avatar"] = account_avatar_path
            logger.info(f"[Setup] ✓ Скачан account_avatar")
        
        # Скачать channel_avatar
        channel_avatar_id = template.get('channel_avatar')
        if channel_avatar_id:
            channel_avatar_path = TEMP_DIR / f"channel_avatar_{template['id']}.jpg"
            await directus.download_file(channel_avatar_id, str(channel_avatar_path))
            files["channel_avatar"] = channel_avatar_path
            logger.info(f"[Setup] ✓ Скачан channel_avatar")
        
        return files
        
    except Exception as e:
        logger.error(f"[Setup] Ошибка скачивания файлов: {e}")
        return files


def generate_random_username(base_name: str, length: int = 6) -> str:
    """
    Сгенерировать случайный username для канала.
    
    Args:
        base_name: Базовое имя канала
        length: Длина случайного суффикса
    
    Returns:
        Уникальный username
    """
    # Очистить base_name от недопустимых символов
    clean_name = ''.join(c for c in base_name if c.isalnum() or c == '_')
    clean_name = clean_name[:20]  # Ограничить длину
    
    # Добавить случайные цифры
    random_suffix = ''.join(random.choices(string.digits, k=length))
    username = f"{clean_name}_{random_suffix}"
    
    return username


async def setup_account_profile(
    client: TelegramClient,
    template: Dict,
    account_avatar_path: Optional[Path]
) -> bool:
    """
    Настроить профиль аккаунта (имя, фамилия, аватар).
    
    Args:
        client: Подключенный Telethon клиент
        template: Шаблон настройки
        account_avatar_path: Путь к аватару аккаунта
    
    Returns:
        True если успешно
    """
    try:
        # Установить имя и фамилию
        first_name = template.get('first_name', 'User')
        last_name = template.get('last_name', '')
        
        await client(UpdateProfileRequest(
            first_name=first_name,
            last_name=last_name
        ))
        logger.info(f"[Setup] ✓ Установлено имя: {first_name} {last_name}")
        
        # Загрузить аватар
        if account_avatar_path and account_avatar_path.exists():
            await client.upload_profile_photo(str(account_avatar_path))
            logger.info(f"[Setup] ✓ Загружен аватар аккаунта")
        
        return True
        
    except FloodWaitError as e:
        logger.warning(f"[Setup] FloodWait при настройке профиля: {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return False
    except Exception as e:
        logger.error(f"[Setup] Ошибка настройки профиля: {e}")
        return False


async def create_channel_with_post(
    client: TelegramClient,
    template: Dict,
    channel_avatar_path: Optional[Path]
) -> Optional[Dict]:
    """
    Создать канал-прокладку с постом и получить ссылку.
    
    Args:
        client: Подключенный Telethon клиент
        template: Шаблон настройки
        channel_avatar_path: Путь к аватару канала
    
    Returns:
        Dict с channel_link и channel_entity или None
    """
    try:
        # 1. Создать канал
        channel_title = template.get('channel_title', 'My Channel')
        channel_description = template.get('channel_description', '')
        
        result = await client(CreateChannelRequest(
            title=channel_title,
            about=channel_description,
            megagroup=False  # Обычный канал, не супергруппа
        ))
        
        channel = result.chats[0]
        logger.info(f"[Setup] ✓ Создан канал: {channel_title} (ID: {channel.id})")
        
        # 2. Загрузить аватар канала
        if channel_avatar_path and channel_avatar_path.exists():
            file = await client.upload_file(str(channel_avatar_path))
            await client(EditPhotoRequest(
                channel=channel,
                photo=InputChatUploadedPhoto(file)
            ))
            logger.info(f"[Setup] ✓ Загружен аватар канала")
        
        # 3. Попытаться создать публичный username
        channel_link = None
        try:
            base_username = template.get('channel_title', 'channel')
            username = generate_random_username(base_username)
            
            await client(UpdateUsernameRequest(
                channel=channel,
                username=username
            ))
            
            channel_link = f"https://t.me/{username}"
            logger.info(f"[Setup] ✓ Создан публичный username: {username}")
            
        except (UsernameOccupiedError, ChannelsAdminPublicTooMuchError, UsernameInvalidError) as e:
            # Фоллбэк на приватную ссылку
            logger.warning(f"[Setup] Не удалось создать публичный username: {e}")
            logger.info(f"[Setup] Использую приватную ссылку...")
            
            invite = await client(ExportChatInviteRequest(peer=channel))
            channel_link = invite.link
            logger.info(f"[Setup] ✓ Создана приватная ссылка: {channel_link}")
        
        # 4. Опубликовать пост с целевой ссылкой
        post_text_template = template.get('post_text_template', '{target_link}')
        target_link = template.get('target_link', 'https://example.com')
        
        post_text = post_text_template.replace('{target_link}', target_link)
        
        await client.send_message(channel, post_text)
        logger.info(f"[Setup] ✓ Опубликован пост в канале")
        
        return {
            "channel_link": channel_link,
            "channel_entity": channel
        }
        
    except FloodWaitError as e:
        logger.warning(f"[Setup] FloodWait при создании канала: {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return None
    except Exception as e:
        logger.error(f"[Setup] Ошибка создания канала: {e}")
        import traceback
        traceback.print_exc()
        return None


async def update_account_bio(
    client: TelegramClient,
    template: Dict,
    channel_link: str
) -> bool:
    """
    Обновить Bio аккаунта со ссылкой на канал.
    
    Args:
        client: Подключенный Telethon клиент
        template: Шаблон настройки
        channel_link: Ссылка на созданный канал
    
    Returns:
        True если успешно
    """
    try:
        account_bio_template = template.get('account_bio_template', '{channel_link}')
        bio = account_bio_template.replace('{channel_link}', channel_link)
        
        await client(UpdateProfileRequest(about=bio))
        logger.info(f"[Setup] ✓ Обновлен Bio аккаунта")
        
        return True
        
    except FloodWaitError as e:
        logger.warning(f"[Setup] FloodWait при обновлении Bio: {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return False
    except Exception as e:
        logger.error(f"[Setup] Ошибка обновления Bio: {e}")
        return False


async def finalize_account_setup(
    account_id: int,
    channel_link: str,
    logs: str
) -> bool:
    """
    Финализировать настройку аккаунта в Directus.
    
    Args:
        account_id: ID аккаунта
        channel_link: Ссылка на созданный канал
        logs: Логи настройки
    
    Returns:
        True если успешно
    """
    try:
        update_data = {
            "personal_channel_url": channel_link,
            "setup_status": "completed",
            "setup_logs": logs,
            "setup_completed_at": datetime.now().isoformat()
        }
        
        await directus.update_item("accounts", account_id, update_data)
        logger.info(f"[Setup] ✓ Аккаунт #{account_id} финализирован в Directus")
        
        return True
        
    except Exception as e:
        logger.error(f"[Setup] Ошибка финализации в Directus: {e}")
        return False


async def mark_account_failed(account_id: int, error_message: str) -> bool:
    """
    Отметить аккаунт как failed в случае ошибки.
    
    Args:
        account_id: ID аккаунта
        error_message: Сообщение об ошибке
    
    Returns:
        True если успешно
    """
    try:
        update_data = {
            "setup_status": "failed",
            "setup_logs": f"Ошибка: {error_message}",
            "setup_failed_at": datetime.now().isoformat()
        }
        
        await directus.update_item("accounts", account_id, update_data)
        logger.info(f"[Setup] ✗ Аккаунт #{account_id} отмечен как failed")
        
        return True
        
    except Exception as e:
        logger.error(f"[Setup] Ошибка обновления статуса failed: {e}")
        return False


async def cleanup_temp_files(files: Dict[str, Optional[Path]]):
    """
    Очистить временные файлы.
    
    Args:
        files: Dict с путями к файлам
    """
    for file_path in files.values():
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"[Setup] 🗑 Удален временный файл: {file_path.name}")
            except Exception as e:
                logger.warning(f"[Setup] Не удалось удалить файл {file_path}: {e}")


async def setup_account_cycle():
    """
    Основной цикл настройки аккаунта:
    1. Получить pending аккаунт
    2. Получить шаблон по setup_template_id или вернуть ошибку
    3. Скачать файлы
    4. Настроить профиль аккаунта
    5. Создать канал с постом
    6. Обновить Bio
    7. Финализировать в Directus
    """
    logger.info("[Setup] Цикл запущен")
    
    try:
        # 1. Получить аккаунт для настройки
        account = await get_pending_account()
        
        if not account:
            logger.info("[Setup] Нет аккаунтов для настройки")
            return
        
        account_id = account['id']
        phone = account['phone']
        
        # 2. Получить шаблон по setup_template_id
        template_id = account.get('template_id')
        
        if not template_id:
            logger.error(f"[Setup] Для аккаунта {phone} не выбран шаблон!")
            await mark_account_failed(account_id, "Шаблон не выбран")
            return
        
        template = await get_template_by_id(template_id)
        
        if not template:
            logger.error(f"[Setup] Шаблон с ID {template_id} не найден для аккаунта {phone}")
            await mark_account_failed(account_id, "Шаблон не найден")
            return
        
        logger.info(f"[Setup] Используется шаблон: {template.get('name', 'Unknown')} (ID: {template_id})")
        
        # 3. Скачать файлы из шаблона
        files = await download_template_files(template)
        
        # 4. Подключиться к Telegram
        client = None
        try:
            session_string = account.get('session_string')
            api_id = int(account['api_id']) if account.get('api_id') else 2040
            api_hash = account.get('api_hash') or "b18441a1ff607e10a989891a5462e627"
            
            if not session_string:
                logger.error(f"[Setup] Аккаунт {phone} не имеет session_string")
                await mark_account_failed(account_id, "Отсутствует session_string")
                return
            
            client = TelegramClient(
                StringSession(session_string),
                api_id,
                api_hash
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.error(f"[Setup] Аккаунт {phone} не авторизован")
                await mark_account_failed(account_id, "Аккаунт не авторизован")
                return
            
            logger.info(f"[Setup] ✓ Подключен к Telegram как {phone}")
            
            # 5. Настроить профиль аккаунта
            profile_success = await setup_account_profile(
                client,
                template,
                files.get("account_avatar")
            )
            
            if not profile_success:
                logger.error(f"[Setup] Не удалось настроить профиль аккаунта {phone}")
                await mark_account_failed(account_id, "Ошибка настройки профиля")
                return
            
            # 6. Создать канал с постом
            channel_result = await create_channel_with_post(
                client,
                template,
                files.get("channel_avatar")
            )
            
            if not channel_result:
                logger.error(f"[Setup] Не удалось создать канал для аккаунта {phone}")
                await mark_account_failed(account_id, "Ошибка создания канала")
                return
            
            channel_link = channel_result["channel_link"]
            
            # 7. Обновить Bio аккаунта
            bio_success = await update_account_bio(client, template, channel_link)
            
            if not bio_success:
                logger.warning(f"[Setup] Не удалось обновить Bio, но продолжаем...")
            
            # 8. Финализировать в Directus
            logs = f"""Успешно настроен аккаунт {phone}
Шаблон: {template.get('name', 'Unknown')} (ID: {template_id})
Канал: {channel_link}
Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            await finalize_account_setup(account_id, channel_link, logs)
            
            logger.info(f"[Setup] ✓✓✓ Аккаунт {phone} успешно настроен!")
            logger.info(f"[Setup]     Канал: {channel_link}")
            logger.info(f"[Setup]     Шаблон: {template.get('name', 'Unknown')} (ID: {template_id})")
            
        except FloodWaitError as e:
            logger.warning(f"[Setup] FloodWait для аккаунта {phone}: {e.seconds}s")
            await mark_account_failed(account_id, f"FloodWait: {e.seconds}s - попробуйте позже")
            
        except Exception as e:
            logger.error(f"[Setup] Ошибка настройки аккаунта {phone}: {e}")
            import traceback
            traceback.print_exc()
            await mark_account_failed(account_id, str(e))
            
        finally:
            if client:
                await client.disconnect()
                logger.info("[Setup] Отключен от Telegram")
            
            # Очистить временные файлы
            await cleanup_temp_files(files)
        
    except Exception as e:
        logger.error(f"[Setup] Критическая ошибка в цикле: {e}")
        import traceback
        traceback.print_exc()


async def run_setup_worker():
    """Главный цикл воркера."""
    logger.info("🚀 Setup Worker запущен")
    logger.info(f"   Интервал проверки: {CHECK_INTERVAL}s")
    logger.info(f"   Временная папка: {TEMP_DIR.absolute()}")
    
    # Login to Directus
    try:
        await directus.login()
        logger.info("✓ Подключение к Directus")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Directus: {e}")
        return
    
    # Main loop
    while True:
        try:
            await setup_account_cycle()
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка в главном цикле: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info(f"💤 Сон {CHECK_INTERVAL}s до следующего цикла...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_setup_worker())
