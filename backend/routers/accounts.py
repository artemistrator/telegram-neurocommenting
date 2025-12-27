"""
Accounts API Router
Handles account management including import with smart proxy assignment
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from typing import Optional
import logging
import os
import tempfile
import zipfile
from pathlib import Path

from backend.directus_client import directus
from backend.services.account_import_service import import_accounts_from_zip
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import FloodWaitError, RPCError
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


async def get_available_proxy():
    """
    Find a free active proxy.
    
    Criteria:
    - status='ok' or status='active'
    - assigned_to IS NULL
    
    Returns:
        Dict with proxy data or None
    """
    try:
        response = await directus.client.get("/items/proxies", params={
            "filter[status][_in]": "ok,active",
            "filter[assigned_to][_null]": "true",
            "limit": 1,
            "fields": "id,host,port,type,username,password"
        })
        
        response.raise_for_status()
        data = response.json()
        proxies = data.get('data', [])
        
        if proxies:
            return proxies[0]
        return None
        
    except Exception as e:
        logger.error(f"Error finding available proxy: {e}")
        return None


async def assign_proxy_to_account(account_id: int, proxy_id: int):
    """
    Bind proxy to account.
    
    Args:
        account_id: Account ID
        proxy_id: Proxy ID
    
    Returns:
        True if successful
    """
    try:
        # Update proxy - set assigned_to
        await directus.update_item("proxies", proxy_id, {
            "assigned_to": account_id
        })
        
        # Update account - set proxy_id
        await directus.update_item("accounts", account_id, {
            "proxy_id": proxy_id
        })
        
        logger.info(f"✓ Proxy {proxy_id} assigned to account {account_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error assigning proxy: {e}")
        return False


@router.post("/import")
async def import_accounts(
    file: UploadFile = File(...),
    auto_assign_proxy: bool = Form(False),
    keep_session_file: bool = Form(False)
):
    """
    Import accounts from ZIP archive using unified service.
    """
    try:
        if not file.filename:
            logger.warning("Import called with empty filename")
            raise HTTPException(status_code=400, detail="Filename is empty")
            
        logger.info(f"Received import request: filename={file.filename}, auto_assign={auto_assign_proxy}")
        content = await file.read()
        logger.info(f"File content read, size={len(content)} bytes")
        results = await import_accounts_from_zip(
            zip_bytes=content,
            filename=file.filename,
            auto_assign_proxy=auto_assign_proxy,
            keep_session_file=keep_session_file
        )
        
        if results["status"] == "error":
            raise HTTPException(status_code=400, detail=results["errors"][0]["detail"])
            
        # Check for proxy errors specifically
        has_proxy_errors = any(error.get("error_code") == "NO_PROXY_AVAILABLE" for error in results["errors"])
        
        if has_proxy_errors:
            return {
                "success": False,
                "imported": results["imported"],
                "errors": len(results["errors"]),
                "message": "❌ Нет доступных прокси. Импортируйте новые прокси перед добавлением аккаунтов.",
                "error_details": results["errors"]
            }
            
        return results
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel

class AccountCreate(BaseModel):
    phone: str
    api_id: int
    api_hash: str
    session_string: Optional[str] = None
    auto_assign_proxy: bool = True


@router.post("/create")
async def create_account(account_in: AccountCreate):
    """
    Manually create an account.
    If auto_assign_proxy is True, tries to find and assign a free proxy.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
            
        # Check if account already exists
        existing = await directus.client.get("/items/accounts", params={
            "filter[phone][_eq]": account_in.phone,
            "fields": "id"
        })
        existing.raise_for_status()
        if existing.json()['data']:
            raise HTTPException(status_code=400, detail=f"Account {account_in.phone} already exists")

        # Create account in Directus
        account_data = {
            "phone": account_in.phone,
            "api_id": account_in.api_id,
            "api_hash": account_in.api_hash,
            "session_string": account_in.session_string,
            "status": "active",
            "setup_status": "pending"
        }
        
        account = await directus.create_item("accounts", account_data)
        account_id = account['id']
        logger.info(f"✓ Created account {account_in.phone}")
        
        # Smart proxy assignment
        proxy_assigned = None
        if account_in.auto_assign_proxy:
            proxy = await get_available_proxy()
            
            if proxy:
                success = await assign_proxy_to_account(account_id, proxy['id'])
                if success:
                    proxy_assigned = proxy
                    logger.info(f"✓ Auto-assigned proxy {proxy['host']} to {account_in.phone}")
            else:
                logger.warning(f"⚠ No available proxies for new account {account_in.phone}")

        return {
            "status": "success",
            "account": account,
            "proxy": proxy_assigned
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_accounts():
    """
    Get list of all accounts with assigned proxies.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
         # DEBUG TOKEN
        print(f"🔑 DEBUG: Token being used: {directus.token}")
        print(f"🔑 DEBUG: Headers: {directus.client.headers}")
        # Get accounts with proxies (using proxy_id field) and setup template
        # Note: We query template_id.id and template_id.name. 
        # We also simplify the response so frontend sees 'proxy' and 'template' objects.
        response = await directus.client.get("/items/accounts", params={
            "fields": "id,phone,first_name,last_name,username,bio,avatar_url,status,setup_status,personal_channel_url,work_mode,warmup_mode,date_updated,template_id.id,template_id.name,proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type,proxy_unavailable",
            "sort": "-date_created"
        })
        
        response.raise_for_status()
        data = response.json().get('data', [])
        
        for acc in data:
            # Rename proxy_id to proxy for frontend
            if 'proxy_id' in acc:
                acc['proxy'] = acc.pop('proxy_id')
            # Map template_id to template for frontend convenience
            if 'template_id' in acc:
                acc['template'] = acc.pop('template_id')
        
        return {
            "status": "success",
            "accounts": data,
            "total": len(data)
        }
        
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{account_id}")
async def delete_account(account_id: int):
    """
    Delete account.
    When deleting, also releases proxy (assigned_to = NULL).
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Get account data
        account_response = await directus.client.get(f"/items/accounts/{account_id}")
        account_response.raise_for_status()
        account = account_response.json()['data']
        
        # If has assigned proxy - release it
        if account.get('proxy_id'):
            await directus.update_item("proxies", account['proxy_id'], {
                "assigned_to": None
            })
            logger.info(f"✓ Proxy {account['proxy_id']} released")
        
        # Delete account
        delete_response = await directus.client.delete(f"/items/accounts/{account_id}")
        delete_response.raise_for_status()
        
        logger.info(f"✓ Account {account_id} deleted")
        
        return {
            'status': 'success',
            'message': f'Account {account_id} deleted'
        }
        
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/check-status")
async def check_account_status(account_id: int):
    """
    Check account status (placeholder for future implementation).
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Get account
        response = await directus.client.get(f"/items/accounts/{account_id}")
        response.raise_for_status()
        account = response.json()['data']
        
        # TODO: Implement actual Telegram status check using Telethon
        # For now, just return current status
        
        return {
            'status': account.get('status', 'unknown'),
            'message': 'Status check completed'
        }
        
    except Exception as e:
        logger.error(f"Error checking account status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RunSetupRequest(BaseModel):
    force: bool = False

@router.post("/{account_id}/run-setup")
async def run_setup(account_id: int, request: RunSetupRequest = RunSetupRequest()):
    """
    Trigger setup process for account.
    This will be picked up by setup_worker.py.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        force = request.force
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"Manual setup requested, force={force}, at {now}"
        if force:
            log_entry += "\nFORCE_SETUP=1"

        # Update account setup_status to pending and add log entry
        await directus.update_item("accounts", account_id, {
            "setup_status": "pending",
            "setup_logs": log_entry
        })
        
        logger.info(f"✓ Setup triggered for account {account_id} (force={force})")
        
        return {
            'status': 'success',
            'message': f'Setup process initiated (force={force}). Worker will process it shortly.'
        }
        
    except Exception as e:
        logger.error(f"Error triggering setup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/rerun-setup")
async def rerun_setup(account_id: int):
    """
    Trigger setup process for account with force=true.
    """
    return await run_setup(account_id, RunSetupRequest(force=True))


@router.post("/{account_id}/assign-proxy")
async def assign_proxy_manually(account_id: int):
    """
    Manually assign a free proxy to account.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        proxy = await get_available_proxy()
        
        if not proxy:
            raise HTTPException(status_code=404, detail="No available proxies")
        
        success = await assign_proxy_to_account(account_id, proxy['id'])
        
        if success:
            return {
                "status": "success",
                "proxy": proxy
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to assign proxy")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning proxy manually: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/release-proxy")
async def release_proxy(account_id: int):
    """
    Release proxy from account.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Get account
        account_response = await directus.client.get(f"/items/accounts/{account_id}")
        account_response.raise_for_status()
        account = account_response.json()['data']
        
        if not account.get('proxy_id'):
            raise HTTPException(status_code=400, detail="Account has no proxy")
        
        # Release proxy
        await directus.update_item("proxies", account['proxy_id'], {
            "assigned_to": None
        })
        
        # Clear proxy_id from account
        await directus.update_item("accounts", account_id, {
            "proxy_id": None
        })
        
        logger.info(f"✓ Proxy released from account {account_id}")
        
        return {
            "status": "success",
            "message": "Proxy released"
        }
        
    except Exception as e:
        logger.error(f"Error releasing proxy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/swap-proxy")
async def swap_proxy(account_id: int):
    """
    Swap current proxy (if dead or requested) to a new free active proxy.
    Safe logic:
    1. Acquire new proxy.
    2. Lock new proxy (assigned_to=account).
    3. Update account (proxy_id=new, proxy_unavailable=False).
    4. Release old proxy (if assigned to this account).
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # 0. Get current account info to know old proxy
        resp = await directus.client.get(f"/items/accounts/{account_id}", params={"fields": "id,proxy_id"})
        resp.raise_for_status()
        account = resp.json()['data']
        old_proxy_id = account.get('proxy_id')

        # 1. Acquire new proxy
        new_proxy = await get_available_proxy()
        if not new_proxy:
             raise HTTPException(status_code=400, detail="NO_PROXY_AVAILABLE")
        
        new_proxy_id = new_proxy['id']
        logger.info(f"Swapping proxy for account {account_id}: found new proxy {new_proxy_id}")

        # 2. Lock new proxy
        await directus.update_item("proxies", new_proxy_id, {"assigned_to": account_id})
        
        # 3. Update account
        await directus.update_item("accounts", account_id, {
            "proxy_id": new_proxy_id,
            "proxy_unavailable": False
        })
        
        # 4. Release old proxy (if it was assigned to this account)
        if old_proxy_id:
            # Check if old proxy is actually assigned to this account before releasing
            # (To avoid race conditions if it was already reassigned manually)
            try:
                p_resp = await directus.client.get(f"/items/proxies/{old_proxy_id}")
                old_p_data = p_resp.json()['data']
                if old_p_data.get('assigned_to') == account_id:
                    await directus.update_item("proxies", old_proxy_id, {"assigned_to": None})
                    logger.info(f"Released old proxy {old_proxy_id}")
            except Exception as e:
                logger.warning(f"Error releasing old proxy {old_proxy_id}: {e}")

        logger.info(f"✓ Swap complete for account {account_id}: {old_proxy_id} -> {new_proxy_id}")
        
        return {
            "status": "success",
            "old_proxy_id": old_proxy_id,
            "new_proxy_id": new_proxy_id,
            "new_proxy": new_proxy
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error swapping proxy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AccountUpdate(BaseModel):
    work_mode: Optional[str] = None
    warmup_mode: Optional[bool] = None
    status: Optional[str] = None
    setup_template_id: Optional[int] = None

@router.patch("/{account_id}")
async def update_account(account_id: int, account_update: AccountUpdate):
    """
    Update account fields.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
            
        # Prepare update data (only include fields that are not None)
        update_data = {}
        if account_update.work_mode is not None:
            update_data["work_mode"] = account_update.work_mode
        if account_update.warmup_mode is not None:
            update_data["warmup_mode"] = account_update.warmup_mode
        if account_update.status is not None:
            update_data["status"] = account_update.status
        if account_update.setup_template_id is not None:
            update_data["setup_template_id"] = account_update.setup_template_id
            
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
            
        # Update account in Directus
        updated_account = await directus.update_item("accounts", account_id, update_data)
        
        logger.info(f"✓ Updated account {account_id} with {update_data}")
        
        return {
            "status": "success",
            "account": updated_account
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/refresh-profile")
async def refresh_profile(account_id: int):
    """
    Refresh profile data from Telegram (First Name, Last Name, Bio, Username).
    """
    client = None
    account_phone = str(account_id) # Safety initialization
    
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()

        # Get account with necessary fields
        response = await directus.client.get(f"/items/accounts/{account_id}", params={
            "fields": "id,phone,api_id,api_hash,session_string,proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type,proxy_id.username,proxy_id.password,proxy_id.status,proxy_id.assigned_to"
        })
        
        try:
            response.raise_for_status()
        except Exception as e:
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Account not found")
            raise e
            
        account = response.json()['data']
        account_phone = account.get('phone') or str(account_id)
        
        # Validation
        if not account.get('session_string'):
            raise HTTPException(status_code=400, detail="Account has no session_string")
        if not account.get('api_id') or not account.get('api_hash'):
            raise HTTPException(status_code=400, detail="Account missing api_id or api_hash")



        # Initialize Telegram Client via factory
        try:
            from backend.services.telegram_client_factory import get_client_for_account, format_proxy
            client = await get_client_for_account(account, directus)
            
            # Safe logging (no credentials)
            proxy_info = account.get('proxy_id')
            if proxy_info:
                print(f"[TG] connect account_id={account_id} phone={account_phone} via {format_proxy(proxy_info)}")
            else:
                print(f"[TG] connect account_id={account_id} phone={account_phone} - no proxy info")
                
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=400, detail=str(e))

        await client.connect()

        if not await client.is_user_authorized():
            raise HTTPException(status_code=400, detail="Account not authorized (session invalid)")

        # Get Me (Basic Info)
        me = await client.get_me()
        
        first_name = me.first_name
        last_name = me.last_name
        username = me.username  # Can be None

        # Get Full Info (Bio)
        bio = ""
        try:
            full = await client(GetFullUserRequest(me))
            if hasattr(full.full_user, 'about'):
                bio = full.full_user.about or ""
        except Exception as e:
            logger.warning(f"Failed to fetch bio for {account_phone}: {e}")

        # Avatar Processing
        temp_file_path = None
        avatar_uuid = None
        try:
            # Create temp file
            # delete=False because we need to close it before re-opening for upload (windows safe)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                temp_file_path = tmp.name
            
            # Download from Telegram
            # download_profile_photo returns the path if successful, or None
            path = await client.download_profile_photo(me, file=temp_file_path)
            
            if path and os.path.exists(path) and os.path.getsize(path) > 0:
                # Upload to Directus
                with open(path, 'rb') as f:
                    files = {'file': (f'avatar_{account_phone}.jpg', f, 'image/jpeg')}
                    # Upload using existing directus client (httpx)
                    upload_response = await directus.client.post("/files", files=files)
                    upload_response.raise_for_status()
                    
                    file_data = upload_response.json()['data']
                    avatar_uuid = file_data['id']
                    logger.info(f"✓ Avatar uploaded for {account_phone}: {avatar_uuid}")
            else:
                logger.info(f"No avatar found or download failed for {account_phone}")

        except Exception as e:
            logger.warning(f"Failed to process avatar for {account_phone}: {e}")
        finally:
            # Cleanup temp file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {temp_file_path}: {e}")

        # Prepare Update Data
        update_data = {
            "first_name": first_name,
            "last_name": last_name,
            "bio": bio,
            "username": username, # Can be None (null in Directus)
        }
            
        # Update avatar if successful
        if avatar_uuid:
            update_data["avatar_url"] = avatar_uuid

        # Update Directus
        await directus.update_item("accounts", account_id, update_data)
        
        logger.info(f"✓ Refreshed profile for account {account_phone}")

        return {
            "status": "success",
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "bio": bio,
            "avatar_url": avatar_uuid
        }

    except FloodWaitError as e:
        logger.warning(f"FloodWait updating profile for {account_phone}: {e.seconds}s")
        # Return 429 with Retry-After header
        raise HTTPException(
            status_code=429, 
            detail=f"FloodWait: {e.seconds} seconds",
            headers={"Retry-After": str(e.seconds)}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing profile for {account_phone}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client for {account_phone}: {e}")
