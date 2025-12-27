import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.workers.setup_worker import setup_account_cycle, directus


async def main():
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/run_setup_once.py <ACCOUNT_ID>")
        sys.exit(1)

    account_id = sys.argv[1]
    
    # Set env var for setup_worker to pick up (though we call setup_account_cycle directly)
    os.environ["SETUP_ACCOUNT_ID"] = account_id
    
    print(f"🚀 Starting setup for account #{account_id}...")
    
    try:
        await directus.login()
        await setup_account_cycle(int(account_id))
        
        # Fetch status to show result
        res = await directus.client.get(f"/items/accounts/{account_id}", params={"fields": "setup_status,setup_logs"})
        data = res.json().get("data", {})
        
        print("\n--- RESULT ---")
        print(f"Status: {data.get('setup_status')}")
        print(f"Logs:\n{data.get('setup_logs')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Give some time for background tasks if any
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
