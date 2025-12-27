#!/usr/bin/env python3
"""
Sanity check script to confirm the Directus client API works.
- Logs in
- Fetches 1 item from accounts via get_items
- Fetches 1 item from subscription_queue via get_items
- Prints OK
"""
import asyncio
import sys
import os

# Add the backend directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.directus_client import directus


async def main():
    print("Testing Directus Client API...")
    
    print("  Logging in...")
    await directus.login()
    
    print("  Fetching 1 item from accounts via get_items...")
    accounts = await directus.get_items("accounts", params={"limit": 1})
    if accounts:
        print(f"  ✓ Got {len(accounts)} account(s)")
    else:
        print("  ! No accounts found, but no error occurred")
    
    print("  Fetching 1 item from subscription_queue via get_items...")
    subscription_queue_items = await directus.get_items("subscription_queue", params={"limit": 1})
    if subscription_queue_items:
        print(f"  ✓ Got {len(subscription_queue_items)} subscription queue item(s)")
    else:
        print("  ! No subscription queue items found, but no error occurred")
    
    # Test the compatibility aliases too
    print("  Testing compatibility alias read_items...")
    accounts_compat = await directus.read_items("accounts", params={"limit": 1})
    if accounts_compat:
        print(f"  ✓ Compatibility alias read_items worked, got {len(accounts_compat)} account(s)")
    else:
        print("  ! No accounts found via read_items alias, but no error occurred")
    
    print("OK")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)