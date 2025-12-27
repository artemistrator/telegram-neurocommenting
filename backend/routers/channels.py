from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import logging
from backend.directus_client import directus

logger = logging.getLogger(__name__)
router = APIRouter()

class SetTemplateRequest(BaseModel):
    template_id: Optional[int]

@router.get("/list")
async def list_channels():
    """Вернуть список каналов для мониторинга с информацией о шаблоне и аккаунте"""
    try:
        # гарантируем логин
        await directus.login()

        # 1. Загружаем каналы с шаблоном
        # Поле template - M2O к setup_templates. Берем его ID и имя.
        try:
            resp_channels = await directus.client.get(
                "/items/channels",
                params={
                    "fields": "id,url,title,subscribers_count,status,source,last_parsed_id,found_channel_id,template.id,template.name",
                    "sort": "-id",
                    "limit": -1, # Загружаем все
                },
            )
            resp_channels.raise_for_status()
            channels_data = resp_channels.json().get("data", [])
        except Exception as e:
            logger.error(f"[Channels API] Error fetching channels from Directus: {e}")
            raise

        # 2. Загружаем аккаунты, чтобы сопоставить шаблоны с аккаунтами
        # У accounts есть поле template_id (M2O -> setup_templates)
        try:
            resp_accounts = await directus.client.get(
                "/items/accounts",
                params={
                    "fields": "id,phone,workmode,template_id",
                    "limit": -1,
                    "filter[status][_eq]": "active" # или без фильтра, если нужны и неактивные
                }
            )
            resp_accounts.raise_for_status()
            accounts_data = resp_accounts.json().get("data", [])
        except Exception as e:
            logger.error(f"[Channels API] Error fetching accounts: {e}")
            # Не падаем, если аккаунты не загрузились, просто не покажем связь
            accounts_data = []

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

        # 3. Собираем итоговый ответ
        results = []
        for ch in channels_data:
            tmpl = ch.get("template") # может быть null или dict {id, name}
            
            # Если шаблон есть, обогащаем его аккаунтом
            if tmpl and isinstance(tmpl, dict):
                t_id = tmpl.get("id")
                # Добавляем инфо об аккаунте
                tmpl["account"] = template_to_account.get(t_id) # dict or None
            else:
                tmpl = None
            
            # Структура канала
            item = {
                "id": ch.get("id"),
                "url": ch.get("url"),
                "title": ch.get("title"),
                "subscribers_count": ch.get("subscribers_count") or 0,
                "status": ch.get("status"),
                "source": ch.get("source"),
                "template": tmpl # {id, name, account: {...}} или null
            }
            results.append(item)

        logger.info(f"[Channels API] Loaded {len(results)} channels with templates")
        return {"channels": results}
    except Exception as e:
        logger.error(f"[Channels API] Error loading channels: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(500, "Failed to load channels")

@router.get("/setup-templates")
async def list_setup_templates_for_dropdown():
    """
    Вернуть список шаблонов setup_templates с привязанными аккаунтами.
    Используется для выпадающего списка на фронте.
    """
    try:
        await directus.login()

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
        await directus.login()

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
                "fields": "id,url,title,subscribers_count,status,source,last_parsed_id,found_channel_id,template.id,template.name"
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