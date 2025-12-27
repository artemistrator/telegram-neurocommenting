"""
Migration helper: Recreate channels for accounts missing personal_channel_id

Usage:
  SETUP_ACCOUNT_ID=123 FORCE_RECREATE_CHANNEL=true python backend/scripts/migrate_channel_ids.py
  
This script will:
1. Check if personal_channel_url exists but personal_channel_id is missing
2. Only recreate channel if FORCE_RECREATE_CHANNEL=true
3. Log warnings to prevent accidental channel duplication
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

directus = DirectusClient()

async def migrate_account(account_id: int):
    """Migrate a single account by recreating its channel if needed."""
    try:
        # Fetch account
        response = await directus.client.get(f"/items/accounts/{account_id}", params={"fields": "*"})
        account = response.json().get('data')
        
        if not account:
            logger.error(f"Account #{account_id} not found")
            return False
        
        personal_channel_url = account.get('personal_channel_url', '').strip()
        personal_channel_id = account.get('personal_channel_id')
        
        logger.info(f"Account #{account_id} ({account.get('phone')})")
        logger.info(f"  personal_channel_url: {personal_channel_url or '(empty)'}")
        logger.info(f"  personal_channel_id: {personal_channel_id or '(empty)'}")
        
        # Check if migration needed
        if not personal_channel_url:
            logger.info("✓ No channel URL - no migration needed")
            return True
        
        if personal_channel_id:
            logger.info("✓ Channel ID already exists - no migration needed")
            return True
        
        # Migration needed
        logger.warning("⚠️ Channel URL exists but channel ID is missing!")
        
        force_recreate = os.getenv("FORCE_RECREATE_CHANNEL", "false").lower() == "true"
        
        if not force_recreate:
            logger.error("❌ FORCE_RECREATE_CHANNEL is not set to 'true'")
            logger.error("   To recreate the channel and get a new ID, run:")
            logger.error(f"   SETUP_ACCOUNT_ID={account_id} FORCE_RECREATE_CHANNEL=true python backend/scripts/migrate_channel_ids.py")
            logger.error("")
            logger.error("   WARNING: This will create a NEW channel. The old channel will remain but won't be tracked.")
            logger.error("   Alternative: Manually update personal_channel_id in Directus with the correct channel ID.")
            return False
        
        logger.warning("🔄 FORCE_RECREATE_CHANNEL=true - will trigger channel recreation")
        logger.warning("   Setting setup_status=pending and clearing personal_channel_url...")
        
        # Clear channel URL and reset status to trigger recreation
        await directus.update_item("accounts", account_id, {
            "setup_status": "pending",
            "personal_channel_url": None,
            "setup_logs": f"Migration: Cleared channel URL to recreate with ID tracking\nOld URL: {personal_channel_url}"
        })
        
        logger.info("✓ Account reset for recreation. Run setup_worker to create new channel.")
        return True
        
    except Exception as e:
        logger.error(f"Error migrating account: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    account_id = os.getenv("SETUP_ACCOUNT_ID")
    
    if not account_id:
        logger.error("SETUP_ACCOUNT_ID environment variable is required")
        sys.exit(1)
    
    try:
        account_id = int(account_id)
    except ValueError:
        logger.error(f"Invalid SETUP_ACCOUNT_ID: {account_id}")
        sys.exit(1)
    
    # Login to Directus
    try:
        await directus.login()
        logger.info("✓ Connected to Directus")
    except Exception as e:
        logger.error(f"Failed to connect to Directus: {e}")
        sys.exit(1)
    
    # Run migration
    success = await migrate_account(account_id)
    
    if success:
        logger.info("✅ Migration completed successfully")
    else:
        logger.error("❌ Migration failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
