from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import logging
import os

# Try to import Directus, fallback to database if not available
try:
    from backend.directus_client import directus
    DIRECTUS_AVAILABLE = True
except Exception:
    DIRECTUS_AVAILABLE = False
    directus = None

logger = logging.getLogger(__name__)
router = APIRouter()

class SetTemplateRequest(BaseModel):
    template_id: Optional[int]

class BulkDeleteRequest(BaseModel):
    channel_ids: List[int]

@router.get("/list")
async def list_channels():
    """Вернуть список каналов для мониторинга с информацией о шаблоне и аккаунте"""
    try:
        logger.info("=== START get_channels_list ===")
        
        # Check if Directus is available
        if not DIRECTUS_AVAILABLE:
            logger.warning("Directus not available, returning empty data")
            return {
                "success": True,
                "channels": [],
                "stats": {
                    "total": 0,
                    "active": 0,
                    "total_comments": 0,
                    "comments_today": 0
                }
            }
        
        logger.info("Using Directus connection")
        return await _get_channels_from_directus()
            
    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_channels_list: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.info("=== END get_channels_list ERROR ===")
        # Return empty data instead of failing completely
        return {
            "success": True,
            "channels": [],
            "stats": {
                "total": 0,
                "active": 0,
                "total_comments": 0,
                "comments_today": 0
            }
        }


async def _get_channels_from_directus():
    """Get channels from Directus"""
    logger.info("Logging into Directus...")
    try:
        await directus.login()
        logger.info("Directus login successful")
    except Exception as e:
        logger.error(f"[Channels API] Error connecting to Directus: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return empty data if Directus is unavailable
        return {
            "success": True,
            "channels": [],
            "stats": {
                "total": 0,
                "active": 0,
                "total_comments": 0,
                "comments_today": 0
            }
        }

    # 1. Загружаем каналы с шаблоном
    # Поле template - M2O к setup_templates. Берем его ID и имя.
    logger.info("Querying channels from Directus...")
    try:
        resp_channels = await directus.client.get(
            "/items/channels",
            params={
                "fields": "id,url,title,subscribers_count,status,source,last_parsed_id,found_channel_id,template.id,template.name,date_created",
                "sort": "-id",
                "limit": -1, # Загружаем все
            },
        )
        logger.info(f"Directus response status: {resp_channels.status_code}")
        resp_channels.raise_for_status()
        channels_data = resp_channels.json().get("data", [])
        logger.info(f"Successfully loaded {len(channels_data)} channels from Directus")
    except Exception as e:
        logger.error(f"[Channels API] Error fetching channels from Directus: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

    # 2. Загружаем аккаунты, чтобы сопоставить шаблоны с аккаунтами
    # У accounts есть поле template_id (M2O -> setup_templates)
    logger.info("Querying accounts from Directus...")
    try:
        resp_accounts = await directus.client.get(
            "/items/accounts",
            params={
                "fields": "id,phone,workmode,template_id",
                "limit": -1,
                "filter[status][_eq]": "active" # или без фильтра, если нужны и неактивные
            }
        )
        logger.info(f"Accounts response status: {resp_accounts.status_code}")
        resp_accounts.raise_for_status()
        accounts_data = resp_accounts.json().get("data", [])
        logger.info(f"Successfully loaded {len(accounts_data)} accounts from Directus")
    except Exception as e:
        logger.error(f"[Channels API] Error fetching accounts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Не падаем, если аккаунты не загрузились, просто не покажем связь
        accounts_data = []

    # 3. Загружаем комментарии для подсчета статистики
    logger.info("Querying comments from Directus...")
    try:
        resp_comments = await directus.client.get(
            "/items/comment_queue",
            params={
                "fields": "id,channel_url,posted_at,status",
                "filter[status][_eq]": "posted", # Only posted comments
                "limit": -1
            }
        )
        logger.info(f"Comments response status: {resp_comments.status_code}")
        resp_comments.raise_for_status()
        comments_data = resp_comments.json().get("data", [])
        logger.info(f"Successfully loaded {len(comments_data)} comments from Directus")
    except Exception as e:
        logger.error(f"[Channels API] Error fetching comments: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Не падаем, если комментарии не загрузились, просто используем пустой список
        comments_data = []

    # Создаем мапу: template_id -> account object
    template_to_account = {}
    for acc in accounts_data:
        t_id = acc.get("template_id")
        if t_id:
            template_to_account[t_id] = {
                "id": acc.get("id"),
                "phone": acc.get("phone"),
                "workmode": acc.get("workmode")
            }

    # Создаем мапу: channel_url -> {count, last_date} для комментариев
    from collections import defaultdict
    comments_by_channel = defaultdict(lambda: {"count": 0, "last_date": None})
    
    for comment in comments_data:
        url = comment.get("channel_url")
        posted_at = comment.get("posted_at")
        
        if url:
            comments_by_channel[url]["count"] += 1
            
            # Track most recent comment
            if posted_at:
                if not comments_by_channel[url]["last_date"] or posted_at > comments_by_channel[url]["last_date"]:
                    comments_by_channel[url]["last_date"] = posted_at

    # 3. Собираем итоговый ответ
    logger.info("Processing channel data...")
    results = []
    for idx, ch in enumerate(channels_data):
        logger.info(f"Processing channel {idx + 1}/{len(channels_data)}: {ch.get('id')}")
        tmpl = ch.get("template") # может быть null или dict {id, name}
        
        # Если шаблон есть, обогащаем его аккаунтом
        if tmpl and isinstance(tmpl, dict):
            t_id = tmpl.get("id")
            logger.info(f"  Channel has template ID: {t_id}")
            # Добавляем инфо об аккаунте
            tmpl["account"] = template_to_account.get(t_id) # dict or None
        else:
            logger.info(f"  Channel has no template")
            tmpl = None
        
        # Получаем данные о комментариях для этого канала
        url = ch.get("url")
        comment_data = comments_by_channel.get(url, {"count": 0, "last_date": None})
        
        # Структура канала
        item = {
            "id": ch.get("id"),
            "url": ch.get("url"),
            "title": ch.get("title"),
            "subscribers_count": ch.get("subscribers_count") or 0,
            "status": ch.get("status"),
            "source": ch.get("source"),
            "date_created": ch.get("date_created"),
            "last_comment_date": comment_data["last_date"],
            "comments_count": comment_data["count"],
            "template": tmpl # {id, name, account: {...}} или null
        }
        results.append(item)
    logger.info(f"Processed {len(results)} channels successfully")

    # Calculate stats
    logger.info("Calculating stats...")
    total = len(results)
    active = len([c for c in results if c.get("status") == "active"])
    
    # Calculate total comments from comment_queue
    total_comments = sum(comment_data["count"] for comment_data in comments_by_channel.values())
    
    # Calculate comments today
    from datetime import datetime, timedelta
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    comments_today = 0
    for comment in comments_data:
        posted_at_str = comment.get("posted_at")
        if posted_at_str:
            try:
                posted_at = datetime.fromisoformat(posted_at_str.replace("Z", "+00:00"))
                if posted_at >= today_start:
                    comments_today += 1
            except Exception as e:
                logger.warning(f"Error parsing comment date {posted_at_str}: {e}")
                continue
    
    logger.info(f"Stats calculated - Total: {total}, Active: {active}, Total Comments: {total_comments}, Comments Today: {comments_today}")
    
    stats = {
        "total": total,
        "active": active,
        "total_comments": total_comments,
        "comments_today": comments_today
    }

    logger.info(f"[Channels API] Loaded {len(results)} channels with templates")
    return {
        "success": True,
        "channels": results,
        "stats": stats
    }


async def _get_channels_fallback():
    """Get channels from database as fallback"""
    # For now, return an empty result as fallback
    logger.info("Using fallback - returning empty results")
    return {
        "success": True,
        "channels": [],
        "stats": {
            "total": 0,
            "active": 0,
            "total_comments": 0,
            "comments_today": 0
        }
    }

@router.get("/setup-templates")
async def list_setup_templates_for_dropdown():
    """
    Вернуть список шаблонов setup_templates с привязанными аккаунтами.
    Используется для выпадающего списка на фронте.
    """
    try:
        if not DIRECTUS_AVAILABLE:
            logger.warning("Directus not available, returning empty templates list")
            return {"templates": []}
        
        logger.info("Logging into Directus for setup-templates...")
        try:
            await directus.login()
        except Exception as e:
            logger.error(f"[Channels API] Error connecting to Directus in setup-templates: {e}")
            return {"templates": []}

        # 1. Загружаем все шаблоны
        resp_tmpl = await directus.client.get(
            "/items/setup_templates",
            params={
                "fields": "id,name",
                "sort": "name",
                "limit": -1
            }
        )
        resp_tmpl.raise_for_status()
        templates = resp_tmpl.json().get("data", [])

        # 2. Загружаем аккаунты
        resp_acc = await directus.client.get(
            "/items/accounts",
            params={
                "fields": "id,phone,template_id",
                "limit": -1
            }
        )
        resp_acc.raise_for_status()
        accounts = resp_acc.json().get("data", [])

        # Мапим template_id -> account info
        # Опять же, берем первый попавшийся или список?
        # Задача: "account_id, account_phone". Предполагаем 1-к-1 или 1-к-N (но показываем один).
        tmpl_map = {}
        for acc in accounts:
            tid = acc.get("template_id")
            if tid:
                tmpl_map[tid] = acc

        # 3. Формируем ответ
        result_list = []
        for t in templates:
            tid = t.get("id")
            acc = tmpl_map.get(tid)
            
            item = {
                "id": tid,
                "name": t.get("name"),
                "account_id": acc.get("id") if acc else None,
                "account_phone": acc.get("phone") if acc else None
            }
            result_list.append(item)

        logger.info(f"[Channels API] Loaded {len(result_list)} templates for dropdown")
        return {"templates": result_list}

    except Exception as e:
        logger.error(f"[Channels API] Error loading templates list: {e}")
        raise HTTPException(500, f"Failed to load templates: {str(e)}")

@router.post("/{channel_id}/set-template")
async def set_channel_template(channel_id: int, body: SetTemplateRequest):
    """
    Привязать или отвязать шаблон от канала.
    """
    try:
        if not DIRECTUS_AVAILABLE:
            logger.error("Directus not available, cannot set template")
            raise HTTPException(500, "Directus service unavailable")
        
        logger.info(f"Logging into Directus for set-template {channel_id}...")
        try:
            await directus.login()
        except Exception as e:
            logger.error(f"[Channels API] Error connecting to Directus in set-template: {e}")
            raise HTTPException(500, "Directus service unavailable")

        # 1. Проверяем существование канала
        # Можно сделать через get, а можно сразу patch. Directus сам вернет ошибку если нет ID.
        # Но чтобы вернуть "Channel not found" красиво, лучше проверить.
        # Для оптимизации сразу делаем PATCH, ловим ошибку?
        # Безопаснее сначала проверить, если нужно вернуть 404.
        # Но тут мы доверяем ID.

        # 2. Если template_id передан — проверим, есть ли такой шаблон?
        # Directus ForeignKey error будет если нет?
        # Если фронт шлет null — это OK.
        
        payload = {
            "template": body.template_id
        }

        # Обновляем канал
        try:
            await directus.update_item("channels", channel_id, payload)
        except Exception as e:
            logger.error(f"[Channels API] Update failed: {e}")
            raise HTTPException(400, f"Failed to update channel: {e}")

        # 3. Возвращаем обновленный объект в том же формате, что и list
        # Это требует повторного запроса.
        # Просто вызовем ту же логику для одного элемента или скопипастим?
        # Скопипастим для эффективности (fetch one channel, fetch one account or reusable map logic).
        
        # Получаем обновленный канал с expand template
        resp_ch = await directus.client.get(
            f"/items/channels/{channel_id}",
            params={
                "fields": "id,url,title,subscribers_count,status,source,template.id,template.name"
            }
        )
        if resp_ch.status_code == 404:
            raise HTTPException(404, "Channel not found")
        resp_ch.raise_for_status()
        ch_data = resp_ch.json().get("data")

        # Если есть шаблон, ищем его аккаунт
        tmpl = ch_data.get("template")
        if tmpl:
            # Ищем аккаунт для этого шаблона
            t_id = tmpl.get("id")
            # Запрос одного аккаунта с фильтром
            resp_acc = await directus.client.get(
                "/items/accounts",
                params={
                    "fields": "id,phone,workmode",
                    "filter[template_id][_eq]": t_id,
                    "limit": 1
                }
            )
            # Не кидаем ошибку если не найден, это допустимо
            acc_list = resp_acc.json().get("data", [])
            if acc_list:
                tmpl["account"] = acc_list[0]
            else:
                tmpl["account"] = None
        
        # Формируем итоговый объект
        result_item = {
            "id": ch_data.get("id"),
            "url": ch_data.get("url"),
            "title": ch_data.get("title"),
            "subscribers_count": ch_data.get("subscribers_count"),
            "status": ch_data.get("status"),
            "source": ch_data.get("source"),
            "template": tmpl 
        }

        logger.info(f"[Channels API] Channel {channel_id} template updated to {body.template_id}")
        return result_item

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Channels API] Error setting template: {e}")
        raise HTTPException(500, str(e))

@router.post("/bulk-delete")
async def bulk_delete_channels(request: BulkDeleteRequest):
    """
    Удалить несколько каналов по ID
    """
    try:
        if not DIRECTUS_AVAILABLE:
            logger.error("Directus not available, cannot bulk delete")
            raise HTTPException(500, "Directus service unavailable")
        
        logger.info("Logging into Directus for bulk-delete...")
        try:
            await directus.login()
        except Exception as e:
            logger.error(f"[Channels API] Error connecting to Directus in bulk-delete: {e}")
            raise HTTPException(500, "Directus service unavailable")
        
        # Validate input
        if not request.channel_ids:
            raise HTTPException(400, "Channel IDs list is empty")
        
        if len(request.channel_ids) > 100:  # Prevent too many deletions at once
            raise HTTPException(400, "Too many channels to delete at once (max 100)")
        
        # Remove duplicates
        unique_channel_ids = list(set(request.channel_ids))
        
        # Delete channels
        deleted_count = 0
        for channel_id in unique_channel_ids:
            try:
                resp = await directus.client.delete(f"/items/channels/{channel_id}")
                resp.raise_for_status()
                deleted_count += 1
            except Exception as e:
                logger.error(f"[Channels API] Error deleting channel {channel_id}: {e}")
                # Continue with other channels instead of failing the whole operation
                continue
        
        logger.info(f"[Channels API] Successfully deleted {deleted_count} channels out of {len(unique_channel_ids)}")
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "requested_count": len(unique_channel_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Channels API] Error bulk deleting channels: {e}")
        raise HTTPException(500, f"Failed to delete channels: {str(e)}")

@router.delete("/{channel_id}")
async def delete_channel(channel_id: int):
    """
    Delete a single channel
    """
    try:
        if not DIRECTUS_AVAILABLE:
            logger.error("Directus not available, cannot delete channel")
            raise HTTPException(500, "Directus service unavailable")
        
        logger.info(f"Logging into Directus for delete {channel_id}...")
        try:
            await directus.login()
        except Exception as e:
            logger.error(f"[Channels API] Error connecting to Directus in delete: {e}")
            raise HTTPException(500, "Directus service unavailable")
        
        # Delete the channel
        resp = await directus.client.delete(f"/items/channels/{channel_id}")
        resp.raise_for_status()
        
        logger.info(f"[Channels API] Channel {channel_id} deleted successfully")
        return {
            "status": "success",
            "message": f"Channel {channel_id} deleted"
        }
        
    except Exception as e:
        logger.error(f"[Channels API] Error deleting channel {channel_id}: {e}")
        raise HTTPException(500, f"Failed to delete channel: {str(e)}")