"""
DEPRECATED: This module is no longer used in the main application flow.
Kept for backwards compatibility. May be removed in future versions.
Date: 2025-12-28
"""

import asyncio
import logging
import os
import random
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional, Any

# Импорты для работы с Directus
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from directus_client import DirectusClient

# Import TaskQueueManager
from backend.services.task_queue_manager import TaskQueueManager
from backend.services.telegram_client_factory import get_client_for_account, format_proxy

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

# Инициализация TaskQueueManager
task_queue_manager = TaskQueueManager()


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
                logger.warning(f"[Subscription] Не удалось сбросить счётчик (полы subscriptions_today может не существовать): {e}")
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


async def subscribe_to_channel_real(account: dict, channel_url: str) -> Tuple[bool, Optional[str]]:
    """
    Реальная подписка на канал через Telethon.
    
    Args:
        account: Данные аккаунта
        channel_url: URL канала для подписки
        
    Returns:
        (success, error_message)
    """
    if not TELETHON_AVAILABLE:
        return False, "Telethon не установлен"

    client = None
    try:
        # Create client via factory (with mandatory proxy)
        try:
            client = await get_client_for_account(account, directus)

            # Safe logging before connect (no credentials)
            proxy = account.get('proxy_id')
            if proxy:
                logger.info(f"[TG] connect account_id={account['id']} phone={account['phone']} via {format_proxy(proxy)}")
            else:
                logger.info(f"[TG] connect account_id={account['id']} phone={account['phone']} - no proxy info")

        except (ValueError, RuntimeError) as e:
            # Factory error: missing proxy, invalid proxy status, etc.
            logger.error(f"[Subscription] Cannot create Telegram client for account {account['id']}: {e}")
            return False, f"Proxy error: {e}"

        await client.connect()

        # Extract username from channel URL
        import re
        # Extract username from URL like https://t.me/username
        match = re.search(r't\.me/([^/]+)', channel_url)
        if match:
            username = match.group(1)
        else:
            # If it's a private link, we can use the URL directly
            if '/+' in channel_url or 'joinchat' in channel_url:
                username = channel_url
            else:
                return False, f"Unable to extract username from URL: {channel_url}"

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


async def process_join_channel_task(task: Dict[str, Any]) -> bool:
    """
    Process a join_channel task from the task queue.
    
    Args:
        task: Task from the task queue with type 'join_channel'
        
    Returns:
        True if successful, False if failed
    """
    try:
        payload = task.get('payload', {})
        subscription_queue_id = payload.get('subscription_queue_id')
        account_id = payload.get('account_id')
        channel_url = payload.get('channel_url')

        if not all([subscription_queue_id, account_id, channel_url]):
            logger.error(f"[Subscription] Missing required data in task payload: {payload}")
            await task_queue_manager.fail_task(task['id'], "Missing required data in task payload")
            return False

        # Получаем данные аккаунта (with proxy fields for factory)
        account_response = await directus.safe_get(
            f"/items/accounts/{account_id}",
            params={"fields": "id,phone,session_string,api_id,api_hash,proxy_unavailable,proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type,proxy_id.username,proxy_id.password,proxy_id.status,proxy_id.assigned_to"}
        )
        account = account_response.json().get('data')

        if not account:
            logger.error(f"[Subscription] ✗ Task #{task['id']}: не найден аккаунт")
            await task_queue_manager.fail_task(task['id'], "Аккаунт не найден")
            return False

        # Guard: Check for proxy unavailability
        if account.get('proxy_unavailable'):
            logger.warning(f"[Subscription] SKIP task #{task['id']} for {account.get('phone')}: Proxy unavailable")
            # We delay the task instead of failing it
            await task_queue_manager.fail_task(task['id'], "Proxy unavailable")
            return False

        # Проверяем лимиты
        if not await check_daily_limit(account):
            await task_queue_manager.fail_task(task['id'], "Исчерпан дневной лимит")
            return False

        if not await check_subscription_delay(account):
            # Schedule the task to run again after 5 minutes
            run_at = datetime.utcnow() + timedelta(minutes=5)
            # Update the task to run again with the new time
            await task_queue_manager.fail_task(task['id'], "Подождать до следующего цикла")
            # For now, we'll just fail and let the scheduler re-create the task later
            return False

        # Рассчитываем задержку
        delay = await calculate_delay(account)

        success = False
        error_message = None

        if MOCK_MODE:
            # DRY RUN режим
            logger.info(f"[DRY RUN] Обработка задачи #{task['id']}: {account.get('phone')} → {channel_url}")
            logger.info(f"[DRY RUN] ✓ Подписался бы на {channel_url} (задержка: {delay}s)")

            # Имитируем задержку (короткую)
            await asyncio.sleep(delay)
            success = True
        else:
            # Реальная подписка
            logger.info(f"[Subscription] Обработка задачи #{task['id']}: {account.get('phone')} → {channel_url}")
            success, error_message = await subscribe_to_channel_real(account, channel_url)

            if success:
                # Реальная задержка
                logger.info(f"[Subscription] Задержка {delay}s перед следующей подпиской...")
                await asyncio.sleep(delay)

        if success:
            # Update subscription queue item to 'subscribed'
            await directus.update_item('subscription_queue', subscription_queue_id, {
                'status': 'subscribed',
                'subscribed_at': datetime.now().isoformat()
            })

            # Обновляем счётчики аккаунта
            new_count = account.get('subscriptions_today', 0) + 1
            try:
                await directus.update_item('accounts', account['id'], {
                    'subscriptions_today': new_count,
                    'last_subscription_at': datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"[Subscription] Не удалось обновить счётчики аккаунта (поля могут не существовать): {e}")

            logger.info(f"[Subscription] ✓ Task #{task['id']} completed (subscribed)")
            
            # Complete the task in the task queue
            await task_queue_manager.complete_task(task['id'])
            return True
        else:
            # Handle FloodWaitError specially - reschedule with the wait time
            if error_message and "FloodWaitError" in error_message:
                import re
                match = re.search(r'(\d+) секунд', error_message)
                if match:
                    wait_seconds = int(match.group(1))
                    run_at = datetime.utcnow() + timedelta(seconds=wait_seconds)
                    # For FloodWait, we'll fail the task but it will be retried at the appropriate time
                    await task_queue_manager.fail_task(task['id'], error_message)
                else:
                    await task_queue_manager.fail_task(task['id'], error_message)
            else:
                # Handle other errors normally
                await task_queue_manager.fail_task(task['id'], error_message)

            logger.error(f"[Subscription] ✗ Task #{task['id']} failed: {error_message}")
            return False

    except Exception as e:
        logger.error(f"[Subscription] ✗ Ошибка обработки задачи #{task['id']}: {e}")
        await task_queue_manager.fail_task(task['id'], str(e))
        return False


async def main():
    """
    Основной цикл воркера, который использует TaskQueueManager для получения задач.
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
    logger.info(f"[Subscription] ✓ Подключение к Directus установлено ({directus.base_url})")

    # Тестовый запрос к subscription_queue
    try:
        test_response = await directus.safe_get("/items/subscription_queue?limit=1")
        if test_response.status_code == 200:
            logger.info("[Subscription] ✓ Проверка доступа к subscription_queue: OK")
        else:
            logger.error(f"[Subscription] ✗ Проверка доступа к subscription_queue: {test_response.status_code} {test_response.text}")
    except Exception as e:
        logger.error(f"[Subscription] ✗ Проверка доступа к subscription_queue: Exception {e}")

    # Main processing loop
    while True:
        try:
            # Claim a join_channel task from the task queue
            task = await task_queue_manager.claim_task(
                worker_id=f"subscription_worker_{os.getpid()}",
                task_types=["join_channel"]
            )

            if task:
                logger.info(f"[Subscription] Claimed task {task['id']} of type {task['type']}")
                await process_join_channel_task(task)
            else:
                # No tasks available, wait before checking again
                logger.info("[Subscription] No join_channel tasks available, waiting...")
                await asyncio.sleep(10)  # Wait 10 seconds before checking again

        except Exception as e:
            logger.error(f"[Subscription] ✗ ERROR в основном цикле: {e}", exc_info=True)
            await asyncio.sleep(10)  # Wait before retrying


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 [Subscription] Worker остановлен пользователем")
