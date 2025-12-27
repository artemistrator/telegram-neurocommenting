from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime

from backend.directus_client import directus
from backend.services.telegram_client_factory import get_client_for_account
import logging

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parser", tags=["parser"])

# Pydantic models
class StartSearchRequest(BaseModel):
    keywords: List[str]
    min_subscribers: int = 100

class AddToMonitoringRequest(BaseModel):
    channel_ids: List[int]

class AddChannelToMonitoringRequest(BaseModel):
    channels: List[dict]

class SearchChannelsRequest(BaseModel):
    keywords: List[str]
    min_subscribers: int = 100
    limit: int = 50

class ManualChannelsRequest(BaseModel):
    urls: List[str]

class AddToMonitoringWithSourceRequest(BaseModel):
    channels: List[dict]
    source: str = "search_parser"  # "search_parser" или "manual"
# Endpoints
@router.post("/start-search")
async def start_search(data: StartSearchRequest):
    """
    Start search process for given keywords.
    Creates 'active' search_keywords entries with frequency 'once'.
    """
    try:
        created_count = 0
        
        for keyword in data.keywords:
            keyword = keyword.strip()
            if not keyword:
                continue
                
            # Prepare data for new keyword
            keyword_data = {
                "keyword": keyword,
                "status": "active",
                "search_frequency": "once",
                "min_subscribers": data.min_subscribers,
                "last_search_at": None,  # Will be set by worker when search starts
                "channels_found": 0
            }
            
            # Create in Directus using DirectusClient
            # We don't need to check for duplicates here as Directus usually handles uniques if configured, 
            # or we just create a new search task. 
            # If we want to avoid duplicates, we could search first.
            # For this task, simple creation is requested.
            
            await directus.create_item("search_keywords", keyword_data)
            created_count += 1
            
        return {"status": "success", "count": created_count}
        
    except Exception as e:
        logger.error(f"Error starting search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results")
async def get_results():
    """
    Get found channels that are pending (not yet processed/added).
    """
    try:
        params = {
            "filter[status][_eq]": "pending",
            "sort": "-subscription_priority",  # Show high priority first
            "limit": -1  # Get all pending
        }
        
        response = await directus.client.get("/items/found_channels", params=params)
        items = response.json().get('data', [])
        
        # Format for frontend
        results = []
        for item in items:
            results.append({
                "id": item.get("id"),
                "title": item.get("channel_title"),
                "username": item.get("channel_username"),
                "url": item.get("channel_url"),
                "subscribers": item.get("subscribers_count"),
                "priority": item.get("subscription_priority"),
                "posts_count": item.get("posts_with_comments", 0),
                "has_comments": item.get("has_comments_enabled", False),
                "keyword_id": item.get("search_keyword_id")
            })
            
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-to-monitoring")
async def add_to_monitoring(request: AddToMonitoringWithSourceRequest):
    """Добавить каналы в мониторинг (channels)"""
    logger.info(f"[Parser API] Add to monitoring: {len(request.channels)} channels, source={request.source}")

    added = []

    for ch in request.channels:
        try:
            # Проверить дубликат по URL
            existing = await directus.client.get("/items/channels", params={
                "filter[url][_eq]": ch['url'],
                "limit": 1
            })
            
            if existing.json().get('data'):
                logger.info(f"  - Skip duplicate: {ch['title']}")
                continue
            
            # Определить found_channel_id (только для search_parser)
            found_channel_id = None
            
            if request.source == 'search_parser':
                # Попытаться найти в found_channels по URL
                found_response = await directus.client.get("/items/found_channels", params={
                    "filter[channel_url][_eq]": ch['url'],
                    "limit": 1
                })
                
                found_data = found_response.json().get('data', [])
                
                if found_data:
                    found_channel_id = found_data[0]['id'] if isinstance(found_data, list) else found_data['id']
                    logger.info(f"  Found existing found_channel: {found_channel_id}")
                else:
                    # Создать запись в found_channels если не существует
                    found_result = await directus.client.post("/items/found_channels", json={
                        'channel_url': ch['url'],
                        'channel_title': ch.get('title', 'Unknown'),
                        'subscribers_count': ch.get('subscribers', 0),
                        'source': 'search'
                    })
                    found_channel_id = found_result.json().get('data', {}).get('id')
                    logger.info(f"  Created found_channel: {found_channel_id}")
            
            # Создать в channels
            channel_data = {
                'url': ch['url'],
                'title': ch.get('title') or ch.get('channel_title') or ch['url'],
                'subscribers_count': ch.get('subscribers') or ch.get('subscribers_count') or 0,
                'has_comments': ch.get('has_comments', False),
                'status': 'active',
                'source': request.source,
                'found_channel_id': found_channel_id  # null для manual
            }
            
            result = await directus.client.post("/items/channels", json=channel_data)
            added.append(result.json().get('data'))
            logger.info(f"  + Added channel: {ch['title']} (source={request.source}, found_id={found_channel_id})")
        
        except Exception as e:
            logger.error(f"  ! Failed to add '{ch.get('title')}': {e}")
            continue

    return {'added': len(added), 'channels': added}

@router.get("/available-listeners")
async def get_available_listeners():
    """Получить список аккаунтов для роли listener"""
    try:
        logger.info("[Parser API] GET /available-listeners called")
        
        # УПРОЩЁННЫЙ ЗАПРОС БЕЗ ФИЛЬТРОВ (для отладки)
        all_accounts = []
        try:
            # First try using the directus wrapper which might have different permissions
            all_accounts = await directus.get_accounts("active")
            logger.info(f"[Parser API] Got {len(all_accounts)} accounts from directus.get_accounts")
        except Exception as wrapper_error:
            logger.error(f"[Parser API] Directus wrapper error: {wrapper_error}")
            
            # Fallback to direct client access
            try:
                response = await directus.client.get("/items/accounts", params={
                    "fields": "id,phone,first_name,last_name,work_mode,status,setup_status"
                })
                
                # Check if we got a successful response
                if response.status_code != 200:
                    logger.error(f"[Parser API] Directus returned status {response.status_code}: {response.text}")
                else:
                    all_accounts = response.json().get('data', [])
                    logger.info(f"[Parser API] Got {len(all_accounts)} accounts from direct client access")
            except Exception as directus_error:
                logger.error(f"[Parser API] Directus client error: {directus_error}")
                all_accounts = []
        
        logger.info(f"[Parser API] Directus returned {len(all_accounts)} total accounts")
        
        # Фильтруем вручную (для отладки)
        filtered = []
        for acc in all_accounts:
            logger.info(f"  Account {acc.get('id')}: status={acc.get('status')}, setup={acc.get('setup_status')}, mode={acc.get('work_mode')}")
            
            # Handle potential None values
            status = acc.get('status') or ''
            setup_status = acc.get('setup_status') or ''
            
            if status == 'active' and setup_status == 'done':
                first_name = acc.get('first_name', '') or ''
                last_name = acc.get('last_name', '') or ''
                name = f"{first_name} {last_name}".strip()
                if not name:
                    name = acc.get('phone', 'Unknown') or 'Unknown'
                
                filtered.append({
                    'id': acc['id'],
                    'phone': acc['phone'],
                    'name': name,
                    'is_listener': acc.get('work_mode') == 'listener'
                })
        
        logger.info(f"[Parser API] Returning {len(filtered)} filtered accounts")
        return filtered
        
    except Exception as e:
        logger.error(f"[Parser API] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load listeners: {str(e)}")

@router.patch("/{account_id}/set-listener")
async def set_listener(account_id: int):
    """Назначить аккаунт listener"""
    try:
        logger.info(f"[Parser API] Setting listener: account_id={account_id}")
        
        # Получить все аккаунты с work_mode='listener'
        response = await directus.client.get("/items/accounts", params={
            "fields": "id,work_mode",
            "filter[work_mode][_eq]": "listener"
        })
        
        current_listeners = response.json().get('data', [])
        logger.info(f"[Parser API] Found {len(current_listeners)} current listeners")
        
        # Сбросить work_mode у всех кроме нового
        for acc in current_listeners:
            if acc['id'] != account_id:
                await directus.client.patch(f"/items/accounts/{acc['id']}", json={
                    'work_mode': 'commenter'
                })
                logger.info(f"[Parser API] Reset listener: account {acc['id']}")
        
        # Установить новому
        await directus.client.patch(f"/items/accounts/{account_id}", json={
            'work_mode': 'listener'
        })
        logger.info(f"[Parser API] Set listener: account {account_id}")
        
        return {"success": True, "listener_id": account_id}
        
    except Exception as e:
        logger.error(f"[Parser API] Error setting listener: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to set listener: {str(e)}")

@router.post("/search-channels")
async def search_channels(data: SearchChannelsRequest):
    """Поиск каналов через Telegram"""
    try:
        # Получить listener
        response = await directus.client.get("/items/accounts", params={
            'filter[work_mode][_eq]': 'listener',
            'limit': 1,
            'fields': 'id,phone,session_string,api_id,api_hash,proxy_id.*'
        })
        
        listeners = response.json().get('data', [])
        
        if not listeners:
            raise HTTPException(400, "No listener account found. Set one first.")

        listener = listeners[0]
        client = await get_client_for_account(listener, directus)

        try:
            await client.connect()
            results = []
            
            # Import Telethon modules here to avoid issues
            from telethon.tl.functions.contacts import SearchRequest as ContactsSearchRequest
            from telethon.tl.functions.channels import GetFullChannelRequest
            
            for keyword in data.keywords:
                # Поиск через Telegram Global Search
                # ФИКС: убрать параметр filter
                search_result = await client(ContactsSearchRequest(
                    q=keyword,
                    limit=data.limit
                ))
                
                for chat in search_result.chats:
                    if not getattr(chat, 'broadcast', False):  # Только каналы
                        continue
                    
                    # Проверить включены ли комменты
                    has_comments = getattr(chat, 'megagroup', False) or hasattr(chat, 'linked_chat_id')
                    
                    if hasattr(chat, 'participants_count') and chat.participants_count >= data.min_subscribers:
                        results.append({
                            'channel_id': chat.id,
                            'title': chat.title,
                            'username': getattr(chat, 'username', None),
                            'subscribers': chat.participants_count,
                            'has_comments': has_comments,  # ← НОВОЕ
                            'url': f"https://t.me/{chat.username}" if hasattr(chat, 'username') else None
                        })
            
            return {'channels': results}

        finally:
            await client.disconnect()
            
    except Exception as e:
        logger.error(f"Error searching channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-manual-channels")
async def add_manual_channels(request: ManualChannelsRequest):
    """Добавить каналы вручную по ссылкам"""
    logger.info(f"[Parser API] Manual add: {len(request.urls)} URLs")
    logger.info(f"  URLs: {request.urls}")
    
    if not request.urls:
        raise HTTPException(400, "URLs list is empty")
    
    # Получить listener
    response = await directus.client.get("/items/accounts", params={
        'filter[work_mode][_eq]': 'listener',
        'limit': 1,
        'fields': 'id,phone,session_string,api_id,api_hash,proxy_id.*'
    })
    
    listeners = response.json().get('data', [])
    
    if not listeners:
        raise HTTPException(400, "No listener account found. Set one first.")

    listener = listeners[0]
    client = await get_client_for_account(listener, directus)

    try:
        await client.connect()
        results = []
        
        # Import Telethon modules here to avoid issues
        from telethon.tl.functions.channels import GetFullChannelRequest
        
        for url in request.urls:
            username = url.strip().rstrip('/').split('/')[-1].replace('@', '')
            logger.info(f"  Resolving: {username}")
            
            entity = await client.get_entity(username)
            
            # Получить full entity для метаданных
            full = await client(GetFullChannelRequest(channel=entity))
            
            results.append({
                'channel_id': entity.id,
                'title': entity.title,
                'username': username,
                'subscribers': getattr(entity, 'participants_count', 0),
                'has_comments': getattr(full.full_chat, 'linked_chat_id', None) is not None,
                'url': f"https://t.me/{username}"
            })
        
        return {'channels': results}

    except Exception as e:
        logger.error(f"Error adding manual channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        await client.disconnect()

@router.post("/add-found-channels")
async def add_found_channels(data: AddToMonitoringRequest):
    """Добавить выбранные каналы в channels (мониторинг)"""
    try:
        # Получить listener для резолва каналов
        response = await directus.client.get("/items/accounts", params={
            'filter[work_mode][_eq]': 'listener',
            'limit': 1,
            'fields': 'id,phone,session_string,api_id,api_hash,proxy_id.*'
        })
        
        listeners = response.json().get('data', [])
        
        if not listeners:
            raise HTTPException(400, "No listener account")

        listener = listeners[0]
        client = await get_client_for_account(listener, directus)

        try:
            await client.connect()
            added = []
            
            for channel_id in data.channel_ids:
                # Резолвим entity
                entity = await client.get_entity(channel_id)
                
                # Создаём в found_channels (не в channels напрямую)
                found_channel = await directus.create_item('found_channels', {
                    'channel_id': str(entity.id),
                    'channel_title': entity.title,
                    'channel_username': getattr(entity, 'username', None),
                    'channel_url': f"https://t.me/{entity.username}" if hasattr(entity, 'username') else None,
                    'subscribers_count': getattr(entity, 'participants_count', 0),
                    'status': 'pending',
                    'source': 'search_parser'
                })
                
                added.append(found_channel)
            
            return {'added': len(added), 'channels': added}

        finally:
            await client.disconnect()
            
    except Exception as e:
        logger.error(f"Error adding found channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-channels-to-monitoring")
async def add_channels_to_monitoring(data: AddChannelToMonitoringRequest):
    """Добавить каналы в мониторинг (принимать has_comments)"""
    try:
        added_count = 0
        errors = []
        
        for ch in data.channels:
            try:
                await directus.client.post("/items/channels", json={
                    'url': ch['url'],
                    'title': ch['title'],
                    'subscribers_count': ch.get('subscribers', 0),
                    'has_comments': ch.get('has_comments', False),  # ← НОВОЕ поле
                    'status': 'active',
                    'source': 'parser'
                })
                added_count += 1
            except Exception as e:
                errors.append(f"Error adding channel {ch.get('title', 'unknown')}: {str(e)}")
                continue
        
        return {
            "added": added_count,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Error adding channels to monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))