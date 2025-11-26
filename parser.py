import asyncio
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel


async def search_channels_by_keywords(
    client: TelegramClient,
    keywords: List[str],
    min_members: int = 0,
    only_with_comments: bool = False,
    max_results_per_keyword: int = 10
) -> List[Dict]:
    """
    Поиск Telegram каналов по ключевым словам
    
    Args:
        client: Авторизованный TelegramClient
        keywords: Список ключевых слов для поиска
        min_members: Минимальное количество подписчиков
        only_with_comments: Фильтровать только каналы с комментариями
        max_results_per_keyword: Максимальное количество результатов на ключевое слово
        
    Returns:
        Список словарей с информацией о найденных каналах
    """
    all_channels = []
    seen_ids = set()
    
    for keyword in keywords:
        try:
            print(f"Поиск по ключевому слову: {keyword}", flush=True)
            
            # Выполнить поиск через Telegram API
            result = await client(SearchRequest(
                q=keyword,
                limit=max_results_per_keyword
            ))
            
            # Обработать результаты
            for chat in result.chats:
                # Фильтровать только каналы и мегагруппы
                if not isinstance(chat, Channel):
                    continue
                
                # Пропустить дубликаты
                if chat.id in seen_ids:
                    continue
                
                # Получить количество подписчиков
                members_count = getattr(chat, 'participants_count', 0) or 0
                
                # Фильтр по минимальному количеству подписчиков
                if members_count < min_members:
                    continue
                
                # Проверить наличие комментариев (discussion group)
                has_comments = hasattr(chat, 'linked_chat_id') and chat.linked_chat_id is not None
                
                # Фильтр по наличию комментариев
                if only_with_comments and not has_comments:
                    continue
                
                # Добавить канал в результаты
                channel_data = {
                    'id': chat.id,
                    'title': chat.title or '',
                    'username': chat.username or '',
                    'members_count': members_count,
                    'has_comments': has_comments,
                    'description': getattr(chat, 'about', '') or '',
                    'keyword': keyword,
                    'is_megagroup': getattr(chat, 'megagroup', False),
                    'is_broadcast': getattr(chat, 'broadcast', False)
                }
                
                all_channels.append(channel_data)
                seen_ids.add(chat.id)
                
                print(f"Найден канал: {channel_data['title']} (@{channel_data['username']}) - {members_count} подписчиков", flush=True)
            
            # Задержка между запросами для предотвращения flood
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Ошибка при поиске по ключевому слову '{keyword}': {e}", flush=True)
            continue
    
    print(f"Всего найдено уникальных каналов: {len(all_channels)}", flush=True)
    return all_channels
