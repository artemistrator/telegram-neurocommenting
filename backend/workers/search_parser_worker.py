"""
Search Parser Worker

Воркер для глобального поиска Telegram-каналов по ключевым словам.
Поддерживает MOCK режим для тестирования без Telegram аккаунтов.
"""

import asyncio
import logging
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel
from telethon.errors import FloodWaitError

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MOCK_MODE = os.getenv('SEARCH_MOCK_MODE', 'true').lower() == 'true'
SEARCH_INTERVAL = int(os.getenv('SEARCH_INTERVAL', '3600'))
SEARCH_MIN_SUBSCRIBERS = int(os.getenv('SEARCH_MIN_SUBSCRIBERS', '1000'))
SEARCH_MAX_RESULTS = int(os.getenv('SEARCH_MAX_RESULTS', '50'))
SEARCH_REQUEST_DELAY_MIN = int(os.getenv('SEARCH_REQUEST_DELAY_MIN', '5'))
SEARCH_REQUEST_DELAY_MAX = int(os.getenv('SEARCH_REQUEST_DELAY_MAX', '10'))

# Initialize Directus client
directus = DirectusClient()

# Mock channel names for testing
MOCK_CHANNEL_NAMES = [
    "Грузоперевозки РФ",
    "Логистика и доставка",
    "Перевозки по России",
    "Cargo Russia",
    "Доставка грузов",
    "Транспорт и логистика",
    "Грузовые перевозки 24/7",
    "Экспресс доставка",
    "Международные перевозки",
    "Логистика Москва",
    "Грузовой транспорт",
    "Перевозки и складирование",
    "Транспортная компания",
    "Логистические решения",
    "Грузоперевозки онлайн",
    "Доставка по всей России",
    "Карго сервис",
    "Логистика и склад",
    "Транспортные услуги",
    "Грузовые автоперевозки"
]


async def should_search_now(keyword_data: Dict) -> bool:
    """
    Проверить нужно ли выполнять поиск для keyword.
    
    Args:
        keyword_data: Данные keyword из search_keywords
    
    Returns:
        True если нужно искать, False если нет
    """
    frequency = keyword_data.get('search_frequency', 'once')
    last_search_at = keyword_data.get('last_search_at')
    
    # Если ещё не искали - нужно искать
    if not last_search_at:
        return True
    
    # Если frequency='once' и уже искали - не нужно
    if frequency == 'once':
        return False
    
    # Парсим last_search_at
    try:
        if isinstance(last_search_at, str):
            last_search = datetime.fromisoformat(last_search_at.replace('Z', '+00:00'))
        else:
            last_search = last_search_at
    except Exception as e:
        logger.warning(f"[Search Parser] Ошибка парсинга last_search_at: {e}, считаем что нужно искать")
        return True
    
    now = datetime.now(last_search.tzinfo) if last_search.tzinfo else datetime.now()
    time_passed = now - last_search
    
    # Проверяем по частоте
    if frequency == 'hourly':
        return time_passed >= timedelta(hours=1)
    elif frequency == 'daily':
        return time_passed >= timedelta(days=1)
    elif frequency == 'weekly':
        return time_passed >= timedelta(weeks=1)
    
    # По умолчанию не искать
    return False


async def generate_mock_channels(keyword: str, count: int = None) -> List[Dict]:
    """
    Генерация фейковых каналов для тестирования.
    
    Args:
        keyword: Ключевое слово для поиска
        count: Количество каналов (если None - случайное 3-5)
    
    Returns:
        Список словарей с данными каналов
    """
    if count is None:
        count = random.randint(3, 5)
    
    channels = []
    used_names = set()
    
    for _ in range(count):
        # Выбираем уникальное название
        while True:
            channel_name = random.choice(MOCK_CHANNEL_NAMES)
            if channel_name not in used_names:
                used_names.add(channel_name)
                break
        
        # Генерируем username
        base_username = channel_name.lower().replace(' ', '_')
        channel_username = f"{base_username}_{random.randint(1, 999)}"
        
        # Случайные данные
        subscribers_count = random.randint(500, 25000)
        has_comments = random.choice([True, False])
        posts_with_comments = random.randint(5, 15) if has_comments else 0
        
        channel_data = {
            'channel_title': channel_name,
            'channel_username': channel_username,
            'channel_url': f"https://t.me/{channel_username}",
            'subscribers_count': subscribers_count,
            'has_comments_enabled': has_comments,
            'last_post_id': random.randint(1000, 9999) if has_comments else None,
            'posts_with_comments': posts_with_comments
        }
        
        channels.append(channel_data)
    
    logger.info(f"[MOCK] Сгенерировано {count} фейковых каналов")
    return channels


async def get_search_account() -> Optional[Dict]:
    """
    Найти подходящий аккаунт для поиска.
    Критерии: active, work_mode IN [listener, commenter].
    Prefer listener (sort -work_mode).
    
    Returns:
        Данные аккаунта или None
    """
    try:
        params = {
            "filter[status][_eq]": "active",
            "filter[work_mode][_in]": "listener,commenter",
            "filter[proxy_unavailable][_neq]": "true",
            "fields": "id,phone,session_string,api_id,api_hash,proxy_unavailable,proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type,proxy_id.username,proxy_id.password,proxy_id.status,proxy_id.assigned_to",
            "sort": "-work_mode",
            "limit": 1
        }
        
        response = await directus.safe_get("/items/accounts", params=params)
        data = response.json().get('data', [])
        
        if data:
            return data[0]
        
        logger.warning("[Search Parser] Не найдено активных аккаунтов для поиска")
        return None
        
    except Exception as e:
        logger.error(f"[Search Parser] Ошибка поиска аккаунта: {e}")
        return None


async def search_telegram_real(keyword: str, min_subscribers: int) -> List[Dict]:
    """
    Реальный поиск в Telegram через Telethon.
    
    Args:
        keyword: Ключевое слово для поиска
        min_subscribers: Минимальное количество подписчиков
    
    Returns:
        Список найденных каналов
    """
    account = await get_search_account()
    if not account:
        return []

    if account.get('proxy_unavailable'):
        logger.warning(f"[Search Parser] SKIP account {account.get('phone')}: Proxy unavailable")
        return []

    logger.info(f"[Search Parser] Используем аккаунт {account.get('phone')} для поиска '{keyword}'")

    try:
        # Create client via factory (with mandatory proxy)
        try:
            from backend.services.telegram_client_factory import get_client_for_account, format_proxy
            
            client = await get_client_for_account(account, directus)
            
            # Safe logging before connect (no credentials)
            proxy = account.get('proxy_id')
            if proxy:
                logger.info(f"[TG] connect account_id={account['id']} phone={account['phone']} via {format_proxy(proxy)}")
            else:
                logger.info(f"[TG] connect account_id={account['id']} phone={account['phone']} - no proxy info")
                
        except (ValueError, RuntimeError) as e:
            # Factory error: missing proxy, invalid proxy status, etc.
            logger.error(f"[Search Parser] Cannot create Telegram client for account {account['id']}: {e}")
            logger.info("[Search Parser] Skipping search due to proxy error")
            return []
        
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error(f"[Search Parser] Аккаунт {account.get('phone')} не авторизован!")
            await client.disconnect()
            return []

        found_channels = []
        
        try:
            # Выполняем поиск
            result = await client(SearchRequest(
                q=keyword,
                limit=SEARCH_MAX_RESULTS
            ))
            
            # Обрабатываем результаты
            # SearchRequest возвращает contacts.Found, который содержит lists: results, chats, users
            for chat in result.chats:
                try:
                    # Нас интересуют только каналы (и супергруппы)
                    if not isinstance(chat, Channel):
                        continue
                    
                    # Пропускаем каналы без юзернейма (не можем сформировать ссылку)
                    if not chat.username:
                        continue
                        
                    # Получаем количество подписчиков (если доступно)
                    subscribers_count = getattr(chat, 'participants_count', 0)
                    if subscribers_count is None:
                        subscribers_count = 0
                        
                    # Собираем данные
                    channel_data = {
                        'channel_title': chat.title,
                        'channel_username': chat.username,
                        'channel_url': f"https://t.me/{chat.username}",
                        'subscribers_count': subscribers_count,
                        'has_comments_enabled': True,  # Считаем True по умолчанию, как просили
                        'last_post_id': None,  # Можно получить через GetHistoryRequest, но это доп. запрос
                        'posts_with_comments': 0  # Placeholder
                    }
                    
                    found_channels.append(channel_data)
                    
                except Exception as e:
                    logger.error(f"[Search Parser] Ошибка парсинга чата {chat.id}: {e}")
                    continue

        except FloodWaitError as e:
            logger.warning(f"[Search Parser] FloodWaitError: ждите {e.seconds} сек")
            # Можно сделать sleep, но лучше скипнуть этот цикл
        except Exception as e:
            logger.error(f"[Search Parser] Ошибка запроса SearchRequest: {e}")
            
        finally:
            await client.disconnect()
            
        return found_channels

    except Exception as e:
        logger.error(f"[Search Parser] Критическая ошибка Telethon: {e}")
        return []


async def search_telegram(keyword: str, min_subscribers: int) -> List[Dict]:
    """
    Поиск в Telegram (реальный или mock).
    
    Args:
        keyword: Ключевое слово для поиска
        min_subscribers: Минимальное количество подписчиков
    
    Returns:
        Список найденных каналов
    """
    if MOCK_MODE:
        # Mock режим
        await asyncio.sleep(random.uniform(1, 2))  # Имитация задержки
        return await generate_mock_channels(keyword)
    else:
        # Реальный режим
        return await search_telegram_real(keyword, min_subscribers)


async def calculate_priority(subscribers: int, posts_with_comments: int) -> int:
    """
    Расчёт приоритета канала.
    
    Формула: (subscribers_count / 1000) + (posts_with_comments * 2)
    Диапазон: 1-10
    
    Args:
        subscribers: Количество подписчиков
        posts_with_comments: Количество постов с комментариями
    
    Returns:
        Приоритет от 1 до 10
    """
    priority = int((subscribers / 1000) + (posts_with_comments * 2))
    return min(10, max(1, priority))


async def channel_exists(channel_url: str) -> bool:
    """
    Проверить существует ли канал в found_channels.
    
    Args:
        channel_url: URL канала
    
    Returns:
        True если канал уже есть в БД
    """
    try:
        params = {
            "filter[channel_url][_eq]": channel_url,
            "limit": 1,
            "fields": "id"
        }
        
        response = await directus.safe_get("/items/found_channels", params=params)
        data = response.json().get('data', [])
        
        return len(data) > 0
        
    except Exception as e:
        logger.error(f"[Search Parser] Ошибка проверки дубликата: {e}")
        return False


async def save_found_channel(keyword_id: int, channel_data: Dict, user_created: Optional[str] = None) -> bool:
    """
    Сохранить найденный канал в found_channels.
    
    Args:
        keyword_id: ID keyword из search_keywords
        channel_data: Данные канала
        user_created: ID пользователя создавшего keyword
    
    Returns:
        True если успешно сохранено
    """
    try:
        # Проверка дубликата
        channel_url = channel_data['channel_url']
        if await channel_exists(channel_url):
            logger.info(f"[Search Parser] ⊘ Канал {channel_url} уже существует, скип")
            return False
        
        # Расчёт приоритета
        priority = await calculate_priority(
            channel_data['subscribers_count'],
            channel_data['posts_with_comments']
        )
        
        # Подготовка данных
        save_data = {
            'search_keyword_id': keyword_id,
            'channel_url': channel_data['channel_url'],
            'channel_username': channel_data['channel_username'],
            'channel_title': channel_data['channel_title'],
            'subscribers_count': channel_data['subscribers_count'],
            'has_comments_enabled': channel_data['has_comments_enabled'],
            'last_post_id': channel_data.get('last_post_id'),
            'posts_with_comments': channel_data['posts_with_comments'],
            'status': 'pending',
            'subscription_priority': priority
        }
        
        if user_created:
            save_data['user_created'] = user_created
        
        # Сохранение
        await directus.create_item('found_channels', save_data)
        
        logger.info(
            f"[Search Parser] ✓ Сохранён канал: {channel_data['channel_title']} "
            f"(приоритет: {priority})"
        )
        return True
        
    except Exception as e:
        logger.error(f"[Search Parser] ERROR: Ошибка сохранения канала: {e}")
        return False


async def process_keyword(keyword_data: Dict) -> None:
    """
    Обработка одного keyword: поиск, фильтрация, сохранение.
    
    Args:
        keyword_data: Данные keyword из search_keywords
    """
    keyword_id = keyword_data['id']
    keyword_text = keyword_data['keyword']
    min_subscribers = keyword_data.get('min_subscribers', SEARCH_MIN_SUBSCRIBERS)
    user_created = keyword_data.get('user_created')
    
    prefix = "[MOCK]" if MOCK_MODE else "[Search Parser]"
    logger.info(f"{prefix} Keyword '{keyword_text}' - начинаем поиск")
    
    try:
        # Проверка нужно ли искать
        if not await should_search_now(keyword_data):
            logger.info(f"{prefix} Keyword '{keyword_text}' - поиск не требуется (по расписанию)")
            return
        
        # Поиск каналов
        channels = await search_telegram(keyword_text, min_subscribers)
        
        if not channels:
            logger.info(f"{prefix} Keyword '{keyword_text}' - каналы не найдены")
            # Обновляем last_search_at даже если ничего не нашли
            await directus.update_item('search_keywords', keyword_id, {
                'last_search_at': datetime.now().isoformat()
            })
            return
        
        logger.info(f"{prefix} Найдено {len(channels)} каналов для '{keyword_text}'")
        
        # Фильтрация и сохранение
        saved_count = 0
        skipped_count = 0
        
        for channel in channels:
            # Фильтр по подписчикам
            if channel['subscribers_count'] < min_subscribers:
                logger.info(
                    f"{prefix} ✗ Скип: @{channel['channel_username']} - "
                    f"мало подписчиков ({channel['subscribers_count']} < {min_subscribers})"
                )
                skipped_count += 1
                continue
            
            # Фильтр по комментариям
            if not channel['has_comments_enabled']:
                logger.info(
                    f"{prefix} ✗ Скип: @{channel['channel_username']} - канал без комментариев"
                )
                skipped_count += 1
                continue
            
            # Логирование канала
            logger.info(
                f"{prefix} Канал @{channel['channel_username']} - "
                f"{channel['subscribers_count']} подписчиков, комментарии: ДА"
            )
            
            # Сохранение
            if await save_found_channel(keyword_id, channel, user_created):
                saved_count += 1
            else:
                skipped_count += 1
            
            # Задержка между сохранениями
            if not MOCK_MODE:
                await asyncio.sleep(random.uniform(
                    SEARCH_REQUEST_DELAY_MIN,
                    SEARCH_REQUEST_DELAY_MAX
                ))
        
        # Обновление keyword
        await directus.update_item('search_keywords', keyword_id, {
            'last_search_at': datetime.now().isoformat(),
            'channels_found': saved_count
        })
        
        logger.info(
            f"{prefix} Keyword '{keyword_text}' завершён: "
            f"{saved_count}/{len(channels)} каналов сохранено"
        )
        
    except Exception as e:
        logger.error(f"{prefix} ERROR: Ошибка обработки keyword '{keyword_text}': {e}")
        import traceback
        traceback.print_exc()


async def get_active_keywords() -> List[Dict]:
    """
    Получить активные keywords из search_keywords.
    
    Returns:
        Список активных keywords
    """
    try:
        params = {
            "filter[status][_eq]": "active",
            "fields": "id,keyword,search_frequency,last_search_at,min_subscribers,user_created",
            "limit": -1
        }
        
        response = await directus.safe_get("/items/search_keywords", params=params)
        keywords = response.json().get('data', [])
        
        logger.info(f"[Search Parser] Найдено {len(keywords)} активных keywords")
        return keywords
        
    except Exception as e:
        logger.error(f"[Search Parser] ERROR: Ошибка получения keywords: {e}")
        return []


async def search_cycle():
    """
    Один цикл поиска: обработка всех активных keywords.
    """
    logger.info("[Search Parser] Цикл поиска запущен")
    
    try:
        # Получить активные keywords
        keywords = await get_active_keywords()
        
        if not keywords:
            logger.info("[Search Parser] Нет активных keywords для обработки")
            return
        
        # Обработать каждый keyword
        for keyword_data in keywords:
            await process_keyword(keyword_data)
            
            # Задержка между keywords
            await asyncio.sleep(2)
        
        logger.info("[Search Parser] ✓ Цикл поиска завершён")
        
    except Exception as e:
        logger.error(f"[Search Parser] ERROR: Ошибка в цикле поиска: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """
    Основной цикл воркера.
    """
    mode = "MOCK" if MOCK_MODE else "REAL"
    logger.info(f"🚀 [Search Parser] Worker запущен, режим: {mode}")
    logger.info(f"   Интервал: {SEARCH_INTERVAL}s")
    logger.info(f"   Мин. подписчиков: {SEARCH_MIN_SUBSCRIBERS}")
    logger.info(f"   Макс. результатов: {SEARCH_MAX_RESULTS}")
    
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
            await search_cycle()
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка в главном цикле: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info(f"💤 Сон {SEARCH_INTERVAL}s до следующего цикла...")
        await asyncio.sleep(SEARCH_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
