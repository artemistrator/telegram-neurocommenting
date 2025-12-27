import os
import json
import asyncio
import zipfile
import tempfile
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from backend.directus_client import directus
from backend.services.telegram_client_factory import build_telethon_proxy

logger = logging.getLogger(__name__)

async def acquire_free_proxy(directus_client, user_created: Optional[str] = None) -> Optional[dict]:
    """
    Find a free active proxy.
    """
    import json
    
    params = {
        "filter": json.dumps({
            "_and": [
                {"status": {"_in": ["active", "ok"]}},
                {"assigned_to": {"_null": True}}
            ]
        }),
        "limit": 1
    }
    
    # Optional: Filter by user ownership if strict isolation needed
    # if user_created:
    #     params["filter"]["_and"].append({"user_created": {"_eq": user_created}})
        
    try:
        resp = await directus_client.client.get("/items/proxies", params=params)
        resp.raise_for_status()
        data = resp.json().get('data', [])
        return data[0] if data else None
    except Exception as e:
        logger.error(f"Error acquiring proxy: {e}")
        return None

# Семафор для предотвращения SQLite locks при одновременном доступе к .session файлам
sqlite_semaphore = asyncio.Semaphore(1)

async def import_accounts_from_zip(
    zip_bytes: bytes, 
    filename: str, 
    auto_assign_proxy: bool, 
    keep_session_file: bool = False,
    tenant_id: Optional[int] = None,
    user_created: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified service for importing accounts from a ZIP archive.
    Used by both API and background workers.
    """
    results = {
        "status": "success",
        "imported": 0,
        "errors": [],
        "accounts": []
    }

    # fallback credentials from env
    env_api_id = os.getenv("TELEGRAM_API_ID")
    env_api_hash = os.getenv("TELEGRAM_API_HASH")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        zip_path = temp_dir_path / filename
        
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)
        
        extract_dir = temp_dir_path / "extracted"
        extract_dir.mkdir()
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            logger.info(f"Zip extracted to {extract_dir}")
        except Exception as e:
            logger.exception(f"Failed to extract zip file {filename}")
            results["status"] = "error"
            results["errors"].append({"file": filename, "error_code": "invalid_zip", "detail": str(e)})
            return results

        # Find all .session files
        session_files = []
        for root, dirs, files in os.walk(str(extract_dir)):
            for file in files:
                if file.endswith(".session"):
                    session_files.append(Path(root) / file)
        
        if not session_files:
            logger.warning("No .session files found in extracted directory")

        logger.info(f"Found {len(session_files)} session files to process")

        for session_path in session_files:
            phone = session_path.stem
            rel_path = str(session_path.relative_to(extract_dir))
            
            try:
                # 1. Check for deduplication
                existing = await directus.client.get("/items/accounts", params={
                    "filter[phone][_eq]": phone,
                    "fields": "id"
                })
                existing.raise_for_status()
                if existing.json().get('data'):
                    results["errors"].append({
                        "phone": phone, 
                        "file": rel_path, 
                        "error_code": "already_exists", 
                        "detail": "Account with this phone already exists"
                    })
                    continue

                # 2. Read device info and API credentials
                device_info = None
                json_path = session_path.with_suffix(".json")
                api_id = None
                api_hash = None


                if json_path.exists():
                    try:
                        logger.info(f"Attempting to parse JSON for {phone}")
                        with open(json_path, 'r', encoding='utf-8') as f:
                            # Read first to log specific content if needed, but standard load is fine
                            device_info = json.load(f)
                            # Extract API credentials if present
                            api_id = device_info.get('api_id') or device_info.get('app_id')
                            api_hash = device_info.get('api_hash') or device_info.get('app_hash')
                            
                            logger.info(f"JSON parsed successfully for {phone}. API_ID={api_id}, Device={device_info.get('device_model')}")
                    except Exception as e:
                        logger.exception(f"Failed to parse JSON for {phone}: {e}")
                        # Try to read raw content for debug
                        try:
                            with open(json_path, 'r', encoding='utf-8', errors='replace') as f:
                                raw_head = f.read(200)
                                logger.error(f"First 200 chars of broken JSON: {raw_head}")
                        except:
                            pass
                        logger.warning(f"Failed to read metadata for {phone}: {e}")

                # Fallback to ENV if missing
                final_api_id = api_id or env_api_id
                final_api_hash = api_hash or env_api_hash

                if not final_api_id or not final_api_hash:
                    results["errors"].append({
                        "phone": phone, 
                        "file": rel_path, 
                        "error_code": "missing_credentials", 
                        "detail": "API ID or API Hash not found in JSON and no fallback in ENV"
                    })
                    continue

                # 3. acquire_free_proxy (moved from step 6)
                proxy = None
                proxy_config = None
                
                if auto_assign_proxy:
                    proxy = await acquire_free_proxy(directus, user_created)
                    if not proxy:
                        raise ValueError("No available proxy found. Please import proxies first.")
                    
                    try:
                        proxy_config = build_telethon_proxy(proxy)
                    except ValueError as e:
                        results["errors"].append({
                            "phone": phone,
                            "file": rel_path,
                            "error_code": "INVALID_PROXY",
                            "detail": f"Acquired proxy is invalid: {e}"
                        })
                        continue

                # 4. Conversion .session -> session_string (Strictly sequential)
                session_string = None
                async with sqlite_semaphore:
                    # Use Factory-compliant instantiation (with proxy if acquired)
                    # If no proxy was acquired but proxy is required, this will cause direct connection
                    # which violates our security policy. We must enforce proxy usage.
                    if not proxy_config:
                        results["errors"].append({
                            "phone": phone,
                            "file": rel_path,
                            "error_code": "NO_PROXY",
                            "detail": "Proxy is required but not available"
                        })
                        continue
                    
                    client = TelegramClient(
                        str(session_path.with_suffix("")), # Telethon appends .session
                        int(final_api_id),
                        final_api_hash,
                        proxy=proxy_config
                    )
                    try:
                        await client.connect()
                        if not await client.is_user_authorized():
                            results["errors"].append({
                                "phone": phone, 
                                "file": rel_path, 
                                "error_code": "invalid_session", 
                                "detail": "Session is not authorized"
                            })
                            # Should we release the proxy here? Typically yes, but we verify next iteration 
                            # or it remains unassigned since we didn't update 'assigned_to' yet.
                            continue
                        
                        session_string = StringSession.save(client.session)
                    except Exception as e:
                        results["errors"].append({
                            "phone": phone, 
                            "file": rel_path, 
                            "error_code": "connection_error", 
                            "detail": str(e)
                        })
                        continue
                    finally:
                        await client.disconnect()

                # 5. Upload session file if requested
                session_file_uuid = None
                if keep_session_file:
                    try:
                        with open(session_path, 'rb') as sf:
                            files = {'file': (f"{phone}.session", sf, 'application/octet-stream')}
                            upload_resp = await directus.client.post("/files", files=files)
                            upload_resp.raise_for_status()
                            session_file_uuid = upload_resp.json()['data']['id']
                    except Exception as e:
                        logger.warning(f"Failed to upload session file for {phone}: {e}")

                # 6. Create account record
                account_data = {
                    "phone": phone,
                    "api_id": int(final_api_id),
                    "api_hash": final_api_hash,
                    "session_string": session_string,
                    "device_info": device_info,
                    "status": "active",
                    "setup_status": "pending",
                    "is_converted": True,
                    "work_mode": "reserve",
                    "user_created": user_created,
                    "session_file": session_file_uuid
                }
                
                if proxy:
                    account_data["proxy_id"] = proxy['id']

                if tenant_id:
                    account_data["tenant_id"] = tenant_id

                logger.info(f"Sending account data to Directus for {phone}...")
                created_account = await directus.create_item("accounts", account_data)
                account_id = created_account['id']
                logger.info(f"Directus response: Account created with ID={account_id}")

                # 7. Finalize Proxy Assignment
                proxy_assigned = False
                if proxy:
                    try:
                        # Update proxy assigned_to
                        # We use filter to ensure we only assign if it's still null (optimistic lock attempt)
                        # But Directus update by ID doesn't easily support conditional update in one go via SDK wrapper usually
                        # But we can try just updating it. If it fails or was taken, we have an issue.
                        
                        await directus.update_item("proxies", proxy['id'], {"assigned_to": account_id})
                        proxy_assigned = True
                    except Exception as e:
                        logger.error(f"Failed to assign proxy {proxy['id']} to {phone}: {e}")
                        # If assignment fails, should we unset proxy_id in account? 
                        # Ideally yes, but let's log it.
                        results["errors"].append({
                             "phone": phone,
                             "file": rel_path,
                             "error_code": "PROXY_ASSIGNMENT_FAILED",
                             "detail": f"Account created but proxy assignment failed: {e}"
                        })

                results["imported"] += 1
                results["accounts"].append({
                    "id": account_id,
                    "phone": phone,
                    "proxy_assigned": proxy_assigned
                })
                
                logger.info(f"Imported account: {phone} (ID: {account_id}, Proxy: {proxy_assigned})")

            except ValueError as e:
                if "No available proxy" in str(e):
                    logger.error(f"No available proxy for {phone}: {e}")
                    results["errors"].append({
                        "phone": phone,
                        "file": rel_path,
                        "error_code": "NO_PROXY_AVAILABLE",
                        "detail": "No available proxy found. Please import proxies first."
                    })
                else:
                    import traceback
                    error_detail = f"{str(e)}\n{traceback.format_exc()}"
                    logger.error(f"Error processing {rel_path}: {error_detail}")
                    results["errors"].append({
                        "phone": phone, 
                        "file": rel_path, 
                        "error_code": "unknown_error", 
                        "detail": str(e) # Keep summary in results
                    })

            except Exception as e:
                import traceback
                error_detail = f"{str(e)}\n{traceback.format_exc()}"
                logger.exception(f"CRITICAL ERROR processing {rel_path}: {e}")
                
                # Try to capture session file start if possible (for debug) although it's binary
                try:
                    with open(session_path, 'rb') as f:
                        head = f.read(200)
                        logger.error(f"Hex dump of session file start (200 bytes): {head.hex()}")
                except:
                    pass

                results["errors"].append({
                    "phone": phone, 
                    "file": rel_path, 
                    "error_code": "unknown_error", 
                    "detail": str(e) # Keep summary in results
                })

    # Summary logs
    logger.info(f"Import finished: {results['imported']} imported, {len(results['errors'])} errors")
    return results
