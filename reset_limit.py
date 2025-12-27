
import asyncio
import os
from datetime import datetime
from backend.directus_client import DirectusClient

async def reset_limit():
    directus = DirectusClient()
    await directus.login()
    
    # Account ID 17 is the one from logs
    account_id = 17
    
    print(f"Resetting limit for account {account_id}...")
    try:
        await directus.update_item('accounts', account_id, {
            'subscriptions_today': 0
        })
        print("✅ Limit reset successfully.")
    except Exception as e:
        print(f"❌ Error resetting limit: {e}")

if __name__ == "__main__":
    asyncio.run(reset_limit())
