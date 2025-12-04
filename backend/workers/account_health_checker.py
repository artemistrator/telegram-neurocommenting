import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    UserDeactivatedError, 
    UserDeactivatedBanError,
    AuthKeyError,
    AuthKeyUnregisteredError
)
from backend.directus_client import directus


async def check_account_health(account):
    """
    Check if a Telegram account is still valid by attempting to connect
    and retrieve user info.
    
    Returns:
        tuple: (is_healthy: bool, error_msg: str or None)
    """
    account_id = account['id']
    session_string = account.get('session_string')
    
    if not session_string:
        return False, "No session_string found"
    
    client = None
    try:
        # Create client from session string
        client = TelegramClient(
            StringSession(session_string),
            account.get('api_id', 2040),
            account.get('api_hash', 'b18441a1ff607e10a989891a5462e627')
        )
        
        await client.connect()
        
        # Try to get user info - this will fail if account is banned/deactivated
        me = await client.get_me()
        
        if me:
            print(f"✅ Account {account_id} ({me.phone}) is healthy")
            return True, None
        else:
            return False, "Unable to retrieve user info"
            
    except (UserDeactivatedError, UserDeactivatedBanError) as e:
        error_msg = f"Account banned/deactivated: {str(e)}"
        print(f"💀 Account {account_id} is DEAD/BANNED: {error_msg}")
        return False, error_msg
        
    except (AuthKeyError, AuthKeyUnregisteredError) as e:
        error_msg = f"Auth key invalid: {str(e)}"
        print(f"🔑 Account {account_id} has invalid auth: {error_msg}")
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"⚠️ Account {account_id} check failed: {error_msg}")
        return False, error_msg
        
    finally:
        if client:
            await client.disconnect()


async def replace_account(banned_account):
    """
    Replace a banned account with a reserve account from the same user.
    
    CRITICAL: Maintains user isolation by only selecting reserves 
    where user_created matches the banned account's user_created.
    
    Args:
        banned_account: The account object that was banned
    """
    banned_id = banned_account['id']
    user_uuid = banned_account.get('user_created')
    work_mode = banned_account.get('work_mode', 'commenter')
    
    if not user_uuid:
        print(f"⚠️ Cannot replace account {banned_id}: no user_created field")
        return
    
    try:
        # Query for reserve accounts belonging to the SAME user
        response = await directus.client.get(
            "/items/accounts",
            params={
                "filter[status][_eq]": "reserve",
                "filter[user_created][_eq]": user_uuid,
                "limit": 1,
                "fields": "id,phone,work_mode"
            }
        )
        response.raise_for_status()
        
        reserves = response.json().get('data', [])
        
        if reserves:
            reserve = reserves[0]
            reserve_id = reserve['id']
            
            # Activate the reserve account with the same work_mode
            await directus.update_item("accounts", reserve_id, {
                "status": "active",
                "work_mode": work_mode
            })
            
            print(f"🔄 REPLACEMENT SUCCESS: Banned Acc {banned_id} replaced by Reserve Acc {reserve_id} for User {user_uuid}")
            print(f"   → Reserve account work_mode set to: {work_mode}")
            
        else:
            print(f"🚨 CRITICAL ALERT: User {user_uuid} has NO RESERVE accounts left!")
            print(f"   → Banned account {banned_id} could not be replaced")
            
    except Exception as e:
        print(f"❌ Error during replacement for account {banned_id}: {e}")
        import traceback
        traceback.print_exc()


async def health_check_cycle():
    """
    Main health check cycle:
    1. Fetch all active accounts
    2. Check each one's health
    3. Mark dead accounts as banned
    4. Trigger replacement for banned accounts
    """
    try:
        # Fetch all active accounts
        print(f"DEBUG: Trying to fetch from: {directus.client.base_url}")
        response = await directus.client.get(
            "/items/accounts",
            params={
                "filter[status][_eq]": "active",
                "fields": "id,session_string,user_created,work_mode,api_id,api_hash,phone"
            }
        )
        
        # Handle token expiration
        if response.status_code == 401:
            print("🔄 Token expired, refreshing...")
            await directus.login()
            return
        
        response.raise_for_status()
        accounts = response.json().get('data', [])
        
        if not accounts:
            print("ℹ️ No active accounts to check")
            return
        
        print(f"\n🔍 Checking {len(accounts)} active account(s)...")
        
        # Check each account
        for account in accounts:
            account_id = account['id']
            
            is_healthy, error_msg = await check_account_health(account)
            
            if not is_healthy:
                # Mark as banned
                print(f"⚠️ Marking account {account_id} as BANNED")
                await directus.update_item("accounts", account_id, {
                    "status": "banned"
                })
                
                # Trigger replacement
                await replace_account(account)
            
            # Small delay between checks to avoid rate limiting
            await asyncio.sleep(2)
        
        print("✅ Health check cycle completed\n")
        
    except Exception as e:
        print(f"❌ Error in health check cycle: {e}")
        import traceback
        traceback.print_exc()


async def run_health_checker():
    """
    Main worker loop - runs health checks every 5 minutes
    """
    print("🏥 Account Health Checker started")
    print("=" * 50)
    
    # Login to Directus
    try:
        await directus.login()
        print("✅ Logged in to Directus successfully\n")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return
    
    # Main loop
    while True:
        try:
            await health_check_cycle()
            
            # Wait 5 minutes before next check
            print("⏳ Waiting 5 minutes until next health check...")
            await asyncio.sleep(300)  # 5 minutes
            
        except KeyboardInterrupt:
            print("\n🛑 Health checker stopped manually")
            break
        except Exception as e:
            print(f"⚠️ Unexpected error in main loop: {e}")
            import traceback
            traceback.print_exc()
            # Wait a bit before retrying to avoid rapid error loops
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(run_health_checker())
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped")
