import asyncio
import logging
import os
import random
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional

# Импорты для работы с Directus
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from directus_client import DirectusClient

# Опционально для реального режима (импортируем только если не в mock режиме)
try:
    from telethon import TelegramClient
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.errors import FloodWaitError, ChannelPrivateError, UserBannedInChannelError
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
MOCK_MODE = os.getenv('SUBSCRIPTION_MOCK_MODE', 'true').lower() == 'true'
SUBSCRIPTION_INTERVAL = int(os.getenv('SUBSCRIPTION_INTERVAL', '300'))  # 5 минут
SUBSCRIPTION_STRATEGY = os.getenv('SUBSCRIPTION_STRATEGY', 'distributed')  # distributed / all / random
SUBSCRIPTION_MAX_PER_CYCLE = int(os.getenv('SUBSCRIPTION_MAX_PER_CYCLE', '5'))

# Инициализация Directus клиента
directus = DirectusClient()


async def check_daily_limit(account: dict) -> bool:
    """
    Проверка лимита подписок на сегодня с автоматическим сбросом счётчика.
    
    Args:
        account: Словарь с данными аккаунта
        
    Returns:
        True если аккаунт может подписываться, False если лимит исчерпан
    """
    today = date.today()
    subscriptions_today = account.get('subscriptions_today', 0)
    max_subscriptions = account.get('max_subscriptions_per_day', 5)
    
    # Если аккаунт в режиме прогрева, уменьшаем лимит вдвое
    if account.get('warmup_mode', False):
        max_subscriptions = max_subscriptions // 2
        logger.info(f"[Subscription] Аккаунт {account.get('phone')} в режиме прогрева, лимит: {max_subscriptions}")
    
    # Проверяем, нужно ли сбросить счётчик
    last_subscription = account.get('last_subscription_at')
    if last_subscription:
        if isinstance(last_subscription, str):
            last_subscription = datetime.fromisoformat(last_subscription.replace('Z', '+00:00'))
        
        # Если последняя подписка была не сегодня, сбрасываем счётчик
        if last_subscription.date() < today:
            logger.info(f"[Subscription] Сброс счётчика для {account.get('phone')} (новый день)")
            try:
                await directus.update_item('accounts', account['id'], {
                    'subscriptions_today': 0
                })
            except Exception as e:
                logger.warning(f"[Subscription] Не удалось сбросить счётчик (поле subscriptions_today может не существовать): {e}")
            subscriptions_today = 0
    
    # Проверяем лимит
    if subscriptions_today >= max_subscriptions:
        logger.warning(f"[Subscription] ⚠ Аккаунт {account.get('phone')} исчерпал лимит ({subscriptions_today}/{max_subscriptions} сегодня)")
        return False
    
    return True


async def check_subscription_delay(account: dict) -> bool:
    """
    Проверка, прошла ли необходимая задержка с момента последней подписки.
    
    Args:
        account: Словарь с данными аккаунта
        
    Returns:
        True если можно подписываться, False если нужно подождать
    """
    last_subscription = account.get('last_subscription_at')
    if not last_subscription:
        return True
    
    if isinstance(last_subscription, str):
        last_subscription = datetime.fromisoformat(last_subscription.replace('Z', '+00:00'))
    
    # Минимальная задержка между подписками (в секундах)
    min_delay = account.get('subscription_delay_min', 180)  # 3 минуты по умолчанию
    
    time_since_last = (datetime.now() - last_subscription.replace(tzinfo=None)).total_seconds()
    
    if time_since_last < min_delay:
        logger.info(f"[Subscription] Аккаунт {account.get('phone')} ещё не готов (прошло {int(time_since_last)}s, нужно {min_delay}s)")
        return False
    
    return True


async def calculate_delay(account: dict) -> int:
    """
    Расчёт задержки для аккаунта (в секундах).
    
    Args:
        account: Словарь с данными аккаунта
        
    Returns:
        Задержка в секундах
    """
    if MOCK_MODE:
        return random.randint(1, 3)
    else:
        delay_min = account.get('subscription_delay_min', 180)  # 3 минуты
        delay_max = account.get('subscription_delay_max', 600)  # 10 минут
        return random.randint(delay_min, delay_max)


async def distribute_channels(channels: List[dict], accounts: List[dict], strategy: str) -> List[Tuple[dict, dict]]:
    """
    Распределение каналов по аккаунтам согласно выбранной стратегии.
    
    Args:
        channels: Список каналов для подписки
        accounts: Список доступных аккаунтов
        strategy: Стратегия распределения (distributed / all / random)
        
    Returns:
        Список пар (account, channel)
    """
    distributions = []
    
    if strategy == 'distributed':
        # Round-robin: каждый аккаунт получает разные каналы
        logger.info(f"[Subscription] Стратегия: distributed (round-robin)")
        for i, channel in enumerate(channels):
            account = accounts[i % len(accounts)]
            distributions.append((account, channel))
            
    elif strategy == 'all':
        # Все аккаунты подписываются на все каналы
        logger.info(f"[Subscription] Стратегия: all (агрессивная)")
        for account in accounts:
            for channel in channels:
                distributions.append((account, channel))
                
    elif strategy == 'random':
        # Случайное распределение
        logger.info(f"[Subscription] Стратегия: random (случайная)")
        for channel in channels:
            account = random.choice(accounts)
            distributions.append((account, channel))
    else:
        logger.error(f"[Subscription] ✗ Неизвестная стратегия: {strategy}, используем 'distributed'")
        return await distribute_channels(channels, accounts, 'distributed')
    
    # Логируем распределение по аккаунтам
    account_stats = {}
    for account, channel in distributions:
        phone = account.get('phone', 'unknown')
        account_stats[phone] = account_stats.get(phone, 0) + 1
    
    for phone, count in account_stats.items():
        logger.info(f"[Subscription] Распределение: Аккаунт {phone} → {count} каналов")
    
    return distributions


async def create_subscription_tasks(distributions: List[Tuple[dict, dict]]) -> int:
    """
    Создание задач в subscription_queue.
    
    Args:
        distributions: Список пар (account, channel)
        
    Returns:
        Количество созданных задач
    """
    created_count = 0
    
    for account, channel in distributions:
        # Проверяем, нет ли уже такой задачи
        params = {
            "filter[account_id][_eq]": account['id'],
            "filter[found_channel_id][_eq]": channel['id'],
            "filter[status][_in]": "pending,processing,subscribed",
            "limit": 1
        }
        response = await directus.client.get("/items/subscription_queue", params=params)
        existing = response.json().get('data', [])
        
        if existing:
            logger.debug(f"[Subscription] Задача для {account.get('phone')} → {channel.get('username')} уже существует")
            continue
        
        # Создаём задачу с небольшой случайной задержкой
        if MOCK_MODE:
            # DRY RUN: обрабатываем сразу
            scheduled_at = datetime.now()
            scheduled_delay = 0 
        else:
            # REAL: с задержкой для распределения нагрузки
            scheduled_delay = random.randint(0, 60)  # 0-60 секунд
            scheduled_at = datetime.now() + timedelta(seconds=scheduled_delay)
        
        task_data = {
            'account_id': account['id'],
            'found_channel_id': channel['id'],
            'status': 'pending',
            'scheduled_at': scheduled_at.isoformat(),
            'retry_count': 0
        }
        
        await directus.create_item('subscription_queue', task_data)
        created_count += 1
        logger.debug(f"[Subscription] Создана задача: {account.get('phone')} → {channel.get('username')} (через {scheduled_delay}s)")
    
    logger.info(f"[Subscription] Создано {created_count} задач в очереди")
    return created_count


async def subscribe_to_channel_real(account: dict, channel: dict) -> Tuple[bool, Optional[str]]:
    """
    Реальная подписка на канал через Telethon.
    
    Args:
        account: Данные аккаунта
        channel: Данные канала
        
    Returns:
        (success, error_message)
    """
    if not TELETHON_AVAILABLE:
        return False, "Telethon не установлен"
    
    client = None
    try:
        # Создаём клиент
        api_id = account.get('api_id')
        api_hash = account.get('api_hash')
        session_string = account.get('session_string')
        
        if not all([api_id, api_hash, session_string]):
            return False, "Отсутствуют данные для авторизации"
        
        from telethon.sessions import StringSession
        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash
        )
        
        await client.connect()
        
        # Получаем username канала
        username = channel.get('username', '').replace('@', '').replace('https://t.me/', '')
        
        if not username:
            return False, "Отсутствует username канала"
        
        # Подписываемся
        await client(JoinChannelRequest(username))
        logger.info(f"[Subscription] ✓ Реальная подписка: {account.get('phone')} → @{username}")
        
        return True, None
        
    except FloodWaitError as e:
        error_msg = f"FloodWaitError: нужно подождать {e.seconds} секунд"
        logger.error(f"[Subscription] ✗ {error_msg}")
        return False, error_msg
        
    except ChannelPrivateError:
        error_msg = "Канал приватный или недоступен"
        logger.error(f"[Subscription] ✗ {error_msg}")
        return False, error_msg
        
    except UserBannedInChannelError:
        error_msg = "Аккаунт забанен"
        logger.error(f"[Subscription] ✗ {error_msg}")
        # Обновляем статус аккаунта
        await directus.update_item('accounts', account['id'], {'status': 'banned'})
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Ошибка подписки: {str(e)}"
        logger.error(f"[Subscription] ✗ {error_msg}")
        return False, error_msg
        
    finally:
        if client:
            await client.disconnect()


async def subscribe_to_channel(task: dict) -> bool:
    """
    Подписка на канал (dry run или реально).
    
    Args:
        task: Задача из subscription_queue
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        # Обновляем статус задачи
        await directus.update_item('subscription_queue', task['id'], {
            'status': 'processing'
        })
        
        # Получаем данные аккаунта и канала
        account_response = await directus.client.get(f"/items/accounts/{task['account_id']}")
        account = account_response.json().get('data')
        
        channel_response = await directus.client.get(f"/items/found_channels/{task['found_channel_id']}")
        channel = channel_response.json().get('data')
        
        if not account or not channel:
            logger.error(f"[Subscription] ✗ Задача #{task['id']}: не найден аккаунт или канал")
            await directus.update_item('subscription_queue', task['id'], {
                'status': 'failed',
                'error_message': 'Аккаунт или канал не найден'
            })
            return False
        
        # Проверяем лимиты
        if not await check_daily_limit(account):
            await directus.update_item('subscription_queue', task['id'], {
                'status': 'failed',
                'error_message': 'Исчерпан дневной лимит'
            })
            return False
        
        if not await check_subscription_delay(account):
            # Переносим задачу на позже
            new_scheduled = datetime.now() + timedelta(minutes=5)
            await directus.update_item('subscription_queue', task['id'], {
                'status': 'pending',
                'scheduled_at': new_scheduled.isoformat()
            })
            return False
        
        # Рассчитываем задержку
        delay = await calculate_delay(account)
        
        success = False
        error_message = None
        
        if MOCK_MODE:
            # DRY RUN режим
            channel_url = channel.get('url', f"https://t.me/{channel.get('username', 'unknown')}")
            logger.info(f"[DRY RUN] Обработка задачи #{task['id']}: {account.get('phone')} → {channel.get('username')}")
            logger.info(f"[DRY RUN] ✓ Подписался бы на {channel_url} (задержка: {delay}s)")
            
            # Имитируем задержку (короткую)
            await asyncio.sleep(delay)
            success = True
        else:
            # Реальная подписка
            logger.info(f"[Subscription] Обработка задачи #{task['id']}: {account.get('phone')} → {channel.get('username')}")
            success, error_message = await subscribe_to_channel_real(account, channel)
            
            if success:
                # Реальная задержка
                logger.info(f"[Subscription] Задержка {delay}s перед следующей подпиской...")
                await asyncio.sleep(delay)
        
        if success:
            # Обновляем задачу
            await directus.update_item('subscription_queue', task['id'], {
                'status': 'subscribed',
                'subscribed_at': datetime.now().isoformat()
            })
            
            # Обновляем канал
            await directus.update_item('found_channels', channel['id'], {
                'status': 'subscribed',
                'subscribed_at': datetime.now().isoformat()
            })
            
            # Создаём запись в channels
            channel_data = {
                'telegram_id': channel.get('telegram_id'),
                'username': channel.get('username'),
                'title': channel.get('title'),
                'description': channel.get('description'),
                'subscribers_count': channel.get('subscribers_count'),
                'source': 'search_parser',
                'found_channel_id': channel['id'],
                'is_active': True
            }
            
            created_channel = await directus.create_item('channels', channel_data)
            logger.info(f"[Subscription] ✓ Канал добавлен в channels (id: {created_channel.get('id')})")
            
            # Обновляем счётчики аккаунта
            new_count = account.get('subscriptions_today', 0) + 1
            try:
                await directus.update_item('accounts', account['id'], {
                    'subscriptions_today': new_count,
                    'last_subscription_at': datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"[Subscription] Не удалось обновить счётчики аккаунта (поля могут не существовать): {e}")
            
            logger.info(f"[Subscription] ✓ Задача #{task['id']} завершена (subscribed)")
            return True
        else:
            # Обработка ошибки
            retry_count = task.get('retry_count', 0) + 1
            
            if retry_count < 3:
                # Повторная попытка через час
                new_scheduled = datetime.now() + timedelta(hours=1)
                await directus.update_item('subscription_queue', task['id'], {
                    'status': 'pending',
                    'retry_count': retry_count,
                    'scheduled_at': new_scheduled.isoformat(),
                    'error_message': error_message
                })
                logger.info(f"[Subscription] Задача #{task['id']} будет повторена (попытка {retry_count}/3)")
            else:
                # Окончательная ошибка
                await directus.update_item('subscription_queue', task['id'], {
                    'status': 'failed',
                    'error_message': error_message,
                    'retry_count': retry_count
                })
                
                # Обновляем статус канала
                if 'private' in (error_message or '').lower():
                    await directus.update_item('found_channels', channel['id'], {
                        'status': 'failed'
                    })
                
                logger.error(f"[Subscription] ✗ Задача #{task['id']} failed: {error_message}")
            
            return False
            
    except Exception as e:
        logger.error(f"[Subscription] ✗ Ошибка обработки задачи #{task['id']}: {e}")
        await directus.update_item('subscription_queue', task['id'], {
            'status': 'failed',
            'error_message': str(e)
        })
        return False


async def process_queue():
    """
    Обработка очереди подписок.
    
    Returns:
        Статистика обработки (subscribed, failed, skipped)
    """
    stats = {'subscribed': 0, 'failed': 0, 'skipped': 0}
    
    try:
        # Берём pending задачи, которые уже можно обрабатывать
        params = {
            "filter[status][_eq]": "pending",
            "filter[scheduled_at][_lte]": datetime.now().isoformat(),
            "sort": "scheduled_at",
            "limit": SUBSCRIPTION_MAX_PER_CYCLE
        }
        response = await directus.client.get("/items/subscription_queue", params=params)
        tasks = response.json().get('data', [])
        
        if not tasks:
            logger.info("[Subscription] Нет задач для обработки")
            return stats
        
        logger.info(f"[Subscription] Найдено {len(tasks)} задач для обработки")
        
        for task in tasks:
            success = await subscribe_to_channel(task)
            
            if success:
                stats['subscribed'] += 1
            else:
                # Проверяем финальный статус задачи
                updated_task_response = await directus.client.get(f"/items/subscription_queue/{task['id']}")
                updated_task = updated_task_response.json().get('data')
                if updated_task.get('status') == 'failed':
                    stats['failed'] += 1
                else:
                    stats['skipped'] += 1
        
        return stats
        
    except Exception as e:
        logger.error(f"[Subscription] ✗ Ошибка обработки очереди: {e}")
        return stats


async def main():
    """
    Основной цикл воркера.
    """
    mode = "DRY RUN" if MOCK_MODE else "REAL"
    logger.info(f"[Subscription] Worker запущен, режим: {mode}")
    logger.info(f"[Subscription] Стратегия: {SUBSCRIPTION_STRATEGY}")
    logger.info(f"[Subscription] Интервал: {SUBSCRIPTION_INTERVAL}s")
    logger.info(f"[Subscription] Макс. подписок за цикл: {SUBSCRIPTION_MAX_PER_CYCLE}")
    
    if not MOCK_MODE and not TELETHON_AVAILABLE:
        logger.error("[Subscription] ✗ ОШИБКА: Telethon не установлен, но режим REAL!")
        logger.error("[Subscription] Установите telethon или включите SUBSCRIPTION_MOCK_MODE=true")
        return
    
    # Логинимся в Directus
    await directus.login()
    logger.info("[Subscription] ✓ Подключение к Directus установлено")
    
    while True:
        try:
            cycle_start = datetime.now()
            logger.info(f"\n{'='*60}")
            logger.info(f"[Subscription] Начало цикла: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            # 1. Берём каналы для подписки
            params = {
                "filter[status][_eq]": "pending",
                "filter[has_comments_enabled][_eq]": "true",
                "sort": "-subscription_priority",
                "limit": 100
            }
            response = await directus.client.get("/items/found_channels", params=params)
            channels = response.json().get('data', [])
            
            if not channels:
                logger.info("[Subscription] Нет каналов для подписки (status='pending')")
            else:
                priorities = [ch.get('subscription_priority', 0) for ch in channels]
                logger.info(f"[Subscription] Найдено {len(channels)} каналов для подписки (приоритет {min(priorities)}-{max(priorities)})")
                
                # 2. Берём доступные аккаунты
                params = {
                    "filter[work_mode][_eq]": "commenter",
                    "filter[status][_eq]": "active"
                }
                response = await directus.client.get("/items/accounts", params=params)
                accounts = response.json().get('data', [])
                
                if not accounts:
                    logger.warning("[Subscription] ⚠ Нет доступных аккаунтов (work_mode='commenter', status='active')")
                else:
                    # Фильтруем аккаунты по лимитам
                    available_accounts = []
                    for account in accounts:
                        if await check_daily_limit(account) and await check_subscription_delay(account):
                            available_accounts.append(account)
                    
                    if not available_accounts:
                        logger.warning("[Subscription] ⚠ Все аккаунты исчерпали лимиты или ещё не готовы")
                    else:
                        logger.info(f"[Subscription] Найдено {len(available_accounts)} доступных аккаунтов")
                        
                        # 3. Распределяем каналы по аккаунтам
                        distributions = await distribute_channels(
                            channels[:SUBSCRIPTION_MAX_PER_CYCLE],
                            available_accounts,
                            SUBSCRIPTION_STRATEGY
                        )
                        
                        # 4. Создаём задачи в очереди
                        if distributions:
                            await create_subscription_tasks(distributions)
            
            # 5. Обрабатываем очередь
            stats = await process_queue()
            
            # Итоги цикла
            cycle_end = datetime.now()
            duration = (cycle_end - cycle_start).total_seconds()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"[Subscription] Цикл завершён за {duration:.1f}s:")
            logger.info(f"  ✓ Подписок: {stats['subscribed']}")
            logger.info(f"  ✗ Ошибок: {stats['failed']}")
            logger.info(f"  ⊘ Пропущено: {stats['skipped']}")
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"[Subscription] ✗ ERROR в основном цикле: {e}", exc_info=True)
        
        # Ждём до следующего цикла
        logger.info(f"[Subscription] Следующий цикл через {SUBSCRIPTION_INTERVAL}s...")
        await asyncio.sleep(SUBSCRIPTION_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 [Subscription] Worker остановлен пользователем")
