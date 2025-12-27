"""
Telegram Account Setup Worker - Refactored to use Task Queue

Uses TaskQueueManager to process setup tasks instead of polling Directus.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import directus
from backend.services.telegram_client_factory import get_client_for_account, format_proxy
from backend.services.account_setup_service import AccountSetupService
from backend.services.task_queue_manager import TaskQueueManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Directus client (using global instance as per project standards)
# directus is already a global instance from backend.directus_client
setup_service: Optional[AccountSetupService] = None
task_manager: Optional[TaskQueueManager] = None

# Configuration
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5"))  # Check more frequently since we're using task queue
TEMP_DIR = Path("temp_setup_files")

# Feature Flags
DRY_RUN = os.getenv("SETUP_DRY_RUN", "false").lower() == "true"
SETUP_ACCOUNT_ID = os.getenv("SETUP_ACCOUNT_ID")


def validate_and_log_setup_status(status: str, context: str = "") -> str:
    """
    Validate and normalize setup_status value before sending to Directus.
    """
    ALLOWED_STATUSES = {"pending", "active", "done", "failed"}
    status = str(status).strip().lower()
    
    # Enforce mapping rules
    if status == "completed":
        status = "done"
    elif status == "in_progress":
        status = "active"
    
    if status not in ALLOWED_STATUSES:
        logger.warning(f"[SETUP_STATUS] Invalid value '{status}', coercing.")
        if "fail" in context.lower() or "error" in context.lower():
            status = "failed"
        else:
            status = "active"
            
    return status


async def mark_account_status(account_id: int, status: str, logs: str = ""):
    """Обновить статус настройки и логи."""
    try:
        validated_status = validate_and_log_setup_status(status, f"mark_account_status(account_id={account_id})")
        
        update_data = {
            "setup_status": validated_status,
            "setup_logs": logs
        }
        
        now_iso = datetime.now().isoformat()
        if validated_status == "active":
            update_data["setup_started_at"] = now_iso
        elif validated_status == "done":
            update_data["setup_completed_at"] = now_iso
        elif validated_status == "failed":
            update_data["setup_failed_at"] = now_iso
            
        await directus.update_item("accounts", account_id, update_data)
    except Exception as e:
        logger.error(f"[Setup] Ошибка обновлениия статуса {status} для {account_id}: {e}")


async def get_template_by_id(template_id: int) -> Optional[Dict]:
    """Получить шаблон по ID."""
    try:
        response = await directus.safe_get(f"/items/setup_templates/{template_id}", params={"fields": "*"})
        if response.status_code == 200:
            return response.json().get('data')
        return None
    except Exception as e:
        logger.error(f"[Setup] Ошибка получения шаблона {template_id}: {e}")
        return None


async def download_template_files(template: Dict) -> Dict[str, Optional[Path]]:
    """Скачать файлы из шаблона во временную папку."""
    TEMP_DIR.mkdir(exist_ok=True)
    files = {"account_avatar": None, "channel_avatar": None}
    
    for key in files.keys():
        file_id = template.get(key)
        if file_id:
            try:
                path = TEMP_DIR / f"{key}_{template['id']}.jpg"
                if not DRY_RUN: # Only download if not dry run, actually service handles dry run check usually but files needed
                    # Wait, if DRY_RUN, do we skip download?
                    # Service logic says "if avatar_path and avatar_path.exists()".
                    # Real files are better even in dry run to simulate existence check.
                    # But directus.download_file might fail locally if auth/network issues?
                    # Let's download them.
                    await directus.download_file(file_id, str(path))
                files[key] = path
            except Exception as e:
                logger.warning(f"[Setup] Failed to download {key}: {e}")
    return files


async def cleanup_temp_files(files: Dict[str, Optional[Path]]):
    """Очистить временные файлы."""
    for file_path in files.values():
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"[Setup] Не удалось удалить файл {file_path}: {e}")


async def setup_account_task(task: Dict[str, Any]):
    """Process a single setup account task."""
    task_id = task['id']
    payload = task.get('payload', {})
    account_id = payload.get('account_id')
    
    if not account_id:
        error_msg = f"Task {task_id} has no account_id in payload"
        logger.error(f"[Setup] {error_msg}")
        await task_manager.log_event(task_id, "error", "failed", error_msg)
        await task_manager.fail_task(task_id, error_msg)
        return
    
    try:
        # Fetch the account details using directus.get_item
        account = await directus.get_item('accounts', account_id)
        if not account:
            error_msg = f"Account {account_id} not found in Directus"
            logger.error(f"[Setup] {error_msg}")
            await task_manager.log_event(task_id, "error", "failed", error_msg)
            await task_manager.fail_task(task_id, error_msg)
            return
        
        phone = account.get('phone', f'ID:{account_id}')
        logger.info(f"[Setup] Processing setup task for account {phone} (ID: {account_id})")
        
        # Guard: Proxy check
        if account.get('proxy_unavailable'):
            error_msg = f"Proxy unavailable for account {phone}"
            logger.warning(f"[Setup] {error_msg}")
            await task_manager.log_event(task_id, "warning", "skipped", error_msg)
            await task_manager.fail_task(task_id, error_msg)
            return

        # Get template
        # Support both int and dict (relation)
        tpl_val = account.get('template_id')
        template_id = tpl_val.get('id') if isinstance(tpl_val, dict) else tpl_val

        if not template_id:
            error_msg = f"Шаблон не выбран для {phone}"
            logger.error(f"[Setup] {error_msg}")
            await mark_account_status(account_id, "failed", "Шаблон не выбран")
            await task_manager.log_event(task_id, "error", "failed", error_msg)
            await task_manager.fail_task(task_id, error_msg)
            return
        
        template = await get_template_by_id(template_id)
        if not template:
            error_msg = f"Шаблон {template_id} не найден"
            logger.error(f"[Setup] {error_msg}")
            await mark_account_status(account_id, "failed", "Шаблон не найден")
            await task_manager.log_event(task_id, "error", "failed", error_msg)
            await task_manager.fail_task(task_id, error_msg)
            return

        # Mark Active
        logger.info(f"[Setup] >>> Start setup {phone} (ID: {account_id}, Tpl: {template_id})")
        await mark_account_status(account_id, "active", f"Start setup with template {template.get('name')}")

        # Download files
        files = await download_template_files(template)
        
        client = None
        try:
            # Connect Telegram
            client = await get_client_for_account(account, directus)
            
            await client.connect()
            if not await client.is_user_authorized():
                raise Exception("Account not authorized")
            
            # Run Service
            success = await setup_service.setup_account(client, account, template, files)
            
            if success:
                # Finalize
                final_msg = "Setup completed successfully via AccountSetupService."
                await mark_account_status(account_id, "done", final_msg)
                logger.info(f"[Setup] ✓✓✓ Account {phone} setup complete!")
                
                # Complete the task
                await task_manager.complete_task(task_id)
                
            else:
                raise Exception("Service returned failure status")
                
        except Exception as e:
            logger.error(f"[Setup] Error setting up {phone}: {e}")
            await mark_account_status(account_id, "failed", f"Error: {e}")
            await task_manager.fail_task(task_id, str(e))
            
        finally:
            if client:
                await client.disconnect()
            await cleanup_temp_files(files)

    except Exception as e:
        logger.error(f"[Setup] Task processing error for task {task_id}: {e}")
        await task_manager.fail_task(task_id, str(e))


async def run_setup_worker():
    """Главный цикл воркера с использованием таск-кью."""
    global setup_service, task_manager
    
    logger.info("🚀 Setup Worker Started (Refactored with Task Queue)")
    if DRY_RUN:
        logger.info("[DRY RUN MODE ENABLED]")
        
    try:
        await directus.login()
        logger.info("✓ Directus connected")
        
        setup_service = AccountSetupService(directus, dry_run=DRY_RUN)
        task_manager = TaskQueueManager()
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        return

    if SETUP_ACCOUNT_ID:
        logger.info(f"🎯 Single run for account #{SETUP_ACCOUNT_ID}")
        # For a specific account, we'd need to create a task first
        # For now, just process tasks as usual
        pass

    worker_id = 'setup-worker'
    task_types = ['setup_account']
    
    logger.info(f"Listening for tasks: {task_types}, worker_id: {worker_id}")
    
    while True:
        try:
            # Claim a task from the queue
            task = await task_manager.claim_task(worker_id, task_types)
            
            if task:
                logger.info(f"Claimed task {task['id']} of type {task['type']}")
                # Process the task
                await setup_account_task(task)
            else:
                # No tasks available, wait before checking again
                await asyncio.sleep(CHECK_INTERVAL)
                
        except Exception as e:
            logger.error(f"❌ Main loop error: {e}")
            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_setup_worker())