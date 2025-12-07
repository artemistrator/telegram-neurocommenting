"""
Telegram Parser Worker

Промежуточный воркер между listener и commenting workers.
Обрабатывает parsed_posts: фильтрует по keywords, генерирует комменты через GPT,
создаёт записи в comment_queue для commenting_worker.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, List

from openai import AsyncOpenAI

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize clients
directus = DirectusClient()
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configuration
CHECK_INTERVAL = 120  # 2 минуты между циклами


async def get_unprocessed_posts(limit: int = 50) -> List[Dict]:
    """
    Получить необработанные посты из parsed_posts.
    
    Возвращает посты со status='published', у которых нет записи в comment_queue.
    """
    try:
        # Получить все опубликованные посты
        params = {
            "filter[status][_eq]": "published",
            "fields": "id,channel_url,post_id,text,user_created",
            "limit": limit,
            "sort": "id"
        }
        
        response = await directus.client.get("/items/parsed_posts", params=params)
        all_posts = response.json().get('data', [])
        
        if not all_posts:
            return []
        
        # Получить все parsed_post_id из comment_queue
        queue_params = {
            "fields": "parsed_post_id",
            "limit": -1
        }
        
        queue_response = await directus.client.get("/items/comment_queue", params=queue_params)
        processed_post_ids = {
            item['parsed_post_id']
            for item in queue_response.json().get('data', [])
            if item.get('parsed_post_id')
        }
        
        # Фильтровать необработанные
        unprocessed = [
            post for post in all_posts
            if post['id'] not in processed_post_ids
        ]
        
        logger.info(f"[Parser] Найдено {len(unprocessed)} необработанных постов (из {len(all_posts)} опубликованных)")
        return unprocessed
        
    except Exception as e:
        logger.error(f"[Parser] Ошибка получения необработанных постов: {e}")
        return []


async def get_available_commenter_account() -> Optional[Dict]:
    """
    Найти свободный аккаунт для комментирования.
    
    Критерии:
    - work_mode='commenter'
    - status='active'
    - commenting_profile_id не null
    """
    try:
        params = {
            "filter[status][_eq]": "active",
            "filter[work_mode][_eq]": "commenter",
            "filter[commenting_profile_id][_nnull]": "true",
            "fields": "id,phone,commenting_profile_id.*",
            "limit": 1
        }
        
        response = await directus.client.get("/items/accounts", params=params)
        accounts = response.json().get('data', [])
        
        if accounts:
            account = accounts[0]
            logger.info(f"[Parser] Найден аккаунт: {account['phone']}")
            return account
        else:
            logger.warning("[Parser] ⚠ Нет свободных аккаунтов для комментирования")
            return None
            
    except Exception as e:
        logger.error(f"[Parser] Ошибка получения аккаунта: {e}")
        return None


def check_keyword_filter(post_text: str, filter_keywords: str) -> bool:
    """
    Проверить текст поста на наличие ключевых слов.
    
    Args:
        post_text: Текст поста
        filter_keywords: Строка с keywords через запятую или список
    
    Returns:
        True если найдено хотя бы одно совпадение
    """
    if not filter_keywords:
        return True
    
    # Обработка разных форматов keywords
    if isinstance(filter_keywords, str):
        keywords = [k.strip().lower() for k in filter_keywords.split(',')]
    elif isinstance(filter_keywords, list):
        keywords = [k.strip().lower() for k in filter_keywords]
    else:
        return True
    
    if not keywords:
        return True
    
    post_lower = post_text.lower()
    
    for keyword in keywords:
        if keyword in post_lower:
            logger.info(f"[Parser] ✓ Keyword matched: '{keyword}'")
            return True
    
    logger.info(f"[Parser] ⊘ Keywords не совпали, скип")
    return False


async def generate_comment(post_text: str, profile: Dict) -> Optional[str]:
    """
    Сгенерировать комментарий через OpenAI GPT-4o-mini.
    
    Args:
        post_text: Текст поста
        profile: Commenting profile с настройками
    
    Returns:
        Сгенерированный комментарий или None при ошибке
    """
    try:
        system_prompt = profile.get('system_prompt', 'You are a helpful commenter.')
        max_words = profile.get('max_words', 50)
        
        user_prompt = f"""Post:
{post_text}

Generate a relevant comment (max {max_words} words)."""
        
        logger.info(f"[Parser] Генерация комментария через GPT-4o-mini...")
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=max_words * 2
        )
        
        comment = response.choices[0].message.content.strip()
        logger.info(f"[Parser] ✓ Комментарий сгенерирован: {comment[:50]}...")
        return comment
        
    except Exception as e:
        logger.error(f"[Parser] ERROR: Ошибка генерации комментария: {e}")
        return None


async def process_post(post: Dict, account: Dict) -> bool:
    """
    Обработать один пост: проверить фильтры, сгенерировать коммент, создать задачу.
    
    Args:
        post: Parsed post dictionary
        account: Account dictionary с профилем
    
    Returns:
        True если задача создана успешно
    """
    post_id = post['id']
    channel_url = post['channel_url']
    telegram_post_id = post['post_id']
    post_text = post['text']
    user_created = post.get('user_created')
    
    logger.info(f"[Parser] Пост #{post_id} проверка фильтров")
    
    # Получить профиль
    profile = account.get('commenting_profile_id')
    if not profile or not isinstance(profile, dict):
        logger.warning(f"[Parser] Пост #{post_id} - нет профиля у аккаунта, скип")
        return False
    
    # Проверить фильтр keywords
    filter_mode = profile.get('filter_mode', 'none')
    
    if filter_mode == 'keywords':
        filter_keywords = profile.get('filter_keywords', '')
        if not check_keyword_filter(post_text, filter_keywords):
            logger.info(f"[Parser] Пост #{post_id} keywords не совпали, скип")
            return False
    
    # Генерировать комментарий
    logger.info(f"[Parser] Пост #{post_id} генерация комментария")
    comment_text = await generate_comment(post_text, profile)
    
    if not comment_text:
        logger.error(f"[Parser] Пост #{post_id} - не удалось сгенерировать комментарий, скип")
        return False
    
    # Создать запись в comment_queue
    try:
        queue_data = {
            "account_id": account['id'],
            "parsed_post_id": post_id,
            "channel_url": channel_url,
            "post_id": telegram_post_id,
            "generated_comment": comment_text,
            "status": "pending",
            "user_created": user_created
        }
        
        response = await directus.client.post("/items/comment_queue", json=queue_data)
        queue_entry = response.json().get('data')
        queue_id = queue_entry['id']
        
        logger.info(f"[Parser] ✓ Пост #{post_id} создана задача comment_queue #{queue_id}")
        return True
        
    except Exception as e:
        logger.error(f"[Parser] ERROR: Пост #{post_id} - ошибка создания задачи: {e}")
        return False


async def parser_cycle():
    """
    Основной цикл парсера:
    1. Получить необработанные посты
    2. Получить свободный аккаунт
    3. Обработать каждый пост
    """
    logger.info("[Parser] Цикл запущен")
    
    try:
        # Получить необработанные посты
        posts = await get_unprocessed_posts()
        
        if not posts:
            logger.info("[Parser] Нет необработанных постов")
            return
        
        # Получить аккаунт для комментирования
        account = await get_available_commenter_account()
        
        if not account:
            logger.warning("[Parser] WARNING: Нет свободных аккаунтов, цикл пропущен")
            return
        
        # Обработать каждый пост
        processed_count = 0
        for post in posts:
            success = await process_post(post, account)
            if success:
                processed_count += 1
            
            # Небольшая задержка между постами
            await asyncio.sleep(1)
        
        logger.info(f"[Parser] ✓ Цикл завершён, обработано {processed_count}/{len(posts)} постов")
        
    except Exception as e:
        logger.error(f"[Parser] ERROR: Ошибка в цикле парсера: {e}")
        import traceback
        traceback.print_exc()


async def run_parser_worker():
    """Главный цикл воркера."""
    logger.info("🚀 Parser Worker запущен")
    logger.info(f"   Интервал проверки: {CHECK_INTERVAL}s")
    logger.info(f"   OpenAI API Key: {'✓ Set' if openai_client.api_key else '✗ Missing'}")
    
    if not openai_client.api_key:
        logger.error("❌ OPENAI_API_KEY не установлен!")
        return
    
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
            await parser_cycle()
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка в главном цикле: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info(f"💤 Сон {CHECK_INTERVAL}s до следующего цикла...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_parser_worker())
