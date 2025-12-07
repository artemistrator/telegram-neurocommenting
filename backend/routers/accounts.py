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
    auto_assign_proxy: bool = Form(False)
):
    """
    Import accounts from ZIP archive.
    
    Args:
        file: ZIP file with .session files
        auto_assign_proxy: Automatically assign free proxies
    
    Returns:
        Import results
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            zip_path = Path(temp_dir) / file.filename
            with open(zip_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Extract ZIP
            extract_dir = Path(temp_dir) / "extracted"
            extract_dir.mkdir()
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find all .session files
            session_files = list(extract_dir.glob("**/*.session"))
            
            imported = 0
            errors = []
            proxies_assigned = 0
            
            for session_file in session_files:
                try:
                    # Extract phone from filename (e.g., "+1234567890.session")
                    phone = session_file.stem
                    
                    # Read session file content (for session_string if needed)
                    # For now, just create account with basic info
                    
                    # Create account in Directus
                    account_data = {
                        "phone": phone,
                        "status": "active",
                        "setup_status": "pending"
                    }
                    
                    account = await directus.create_item("accounts", account_data)
                    account_id = account['id']
                    imported += 1
                    
                    logger.info(f"✓ Imported account: {phone}")
                    
                    # Smart proxy assignment
                    if auto_assign_proxy:
                        proxy = await get_available_proxy()
                        
                        if proxy:
                            success = await assign_proxy_to_account(account_id, proxy['id'])
                            
                            if success:
                                proxies_assigned += 1
                                logger.info(f"✓ Proxy {proxy['host']}:{proxy['port']} → Account {phone}")
                        else:
                            logger.warning(f"⚠ No available proxies for account {phone}")
                    
                except Exception as e:
                    error_msg = f"Error importing {session_file.name}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            return {
                "status": "success",
                "imported": imported,
                "errors": errors,
                "proxies_assigned": proxies_assigned
            }
        
            
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
        # Get accounts with proxies (using proxy_id field)
        response = await directus.client.get("/items/accounts", params={
            "fields": "id,phone,first_name,last_name,bio,avatar_url,status,setup_status,personal_channel_url,work_mode,proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type",
            "sort": "-date_created"
        })
        
        response.raise_for_status()
        data = response.json()
        
        accounts = data.get('data', [])
        
        # Rename proxy_id to proxy for frontend
        for account in accounts:
            if 'proxy_id' in account:
                account['proxy'] = account.pop('proxy_id')
        
        return {
            'accounts': accounts,
            'total': len(accounts)
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


@router.post("/{account_id}/run-setup")
async def run_setup(account_id: int):
    """
    Trigger setup process for account.
    This will be picked up by setup_worker.py.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Update account setup_status to pending
        await directus.update_item("accounts", account_id, {
            "setup_status": "pending"
        })
        
        logger.info(f"✓ Setup triggered for account {account_id}")
        
        return {
            'status': 'success',
            'message': 'Setup process initiated. Worker will process it shortly.'
        }
        
    except Exception as e:
        logger.error(f"Error triggering setup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error releasing proxy: {e}")
        raise HTTPException(status_code=500, detail=str(e))
