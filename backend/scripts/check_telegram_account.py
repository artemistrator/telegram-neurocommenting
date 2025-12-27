
import asyncio
import argparse
import sys
import logging
import os
from pathlib import Path

# Setup path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient
from backend.services.telegram_client_factory import get_client_for_account, format_proxy
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest
from telethon.tl.functions.messages import GetDiscussionMessageRequest

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_account(account_id: int, channel_url: str = None, post_id: int = None):
    """
    Check Telegram account connectivity, enforcing proxy usage.
    Optionally attempts to verify commenting capabilities on a specific post.
    """
    directus = DirectusClient()
    
    print(f"\n🔍 Checking Account ID: {account_id}")
    
    # 1. Login to Directus
    try:
        await directus.login()
        print("  ✓ Directus: Logged in")
    except Exception as e:
        print(f"  ❌ Directus Login Failed: {e}")
        sys.exit(1)

    # 2. Fetch Account
    try:
        # Fetch sensitive fields for proxy validation
        # We use get_items with filters because we want to use the safe parameter handling
        # and ensure we get the item properly expanded with full control.
        # Alternatively, we can use the newly updated get_item with params since we fixed it.
        params = {
            "fields": "id,phone,session_string,api_id,api_hash,status,proxy_id.*"
        }
        item = await directus.get_item("accounts", account_id, params=params)
        
        if not item:
            print(f"  ❌ Account {account_id} not found")
            sys.exit(1)
        
        print(f"  👤 Phone: {item.get('phone')}")
        
    except Exception as e:
        print(f"  ❌ Error fetching account: {e}")
        sys.exit(1)

    # 3. Validate Proxy STRICTLY
    proxy = item.get('proxy_id')
    if not proxy:
         print("  ❌ FATAL: No proxy assigned to account! (proxy_id is NULL)")
         sys.exit(2)
    
    # Check proxy fields
    if not isinstance(proxy, dict):
        # Should be dict because of .* fetch, but strictly check
         print("  ❌ FATAL: Proxy data is not valid object/dict")
         sys.exit(2)

    p_host = proxy.get('host')
    p_port = proxy.get('port')
    p_status = proxy.get('status')
    
    if not p_host or not p_port:
        print("  ❌ FATAL: Proxy host or port is empty!")
        sys.exit(2)
        
    if p_status != 'active':
        print(f"  ❌ FATAL: Proxy status is '{p_status}', expected 'active'")
        sys.exit(2)

    print(f"  🛡 Proxy Check Passed: {item.get('proxy_id').get('type')}://{p_host}:{p_port}")
    # Do not print password
    if proxy.get('username'):
        print("    (Authenticated proxy: username set)")

    print(f"  🛡 Proxy Check Passed: {item.get('proxy_id').get('type')}://{p_host}:{p_port}")
    if proxy.get('username'):
        print("    (Authenticated proxy: username set)")

    # 4. Connect Telegram Client
    client = None
    try:
        print("\n  🔌 Connecting to Telegram (via proxy check in factory)...")
        # Factory enforces proxy by default. Removed force_proxy arg as it does not exist in signature.
        client = await get_client_for_account(item, directus)
        
        await client.connect()
        
        connected = client.is_connected()
        
        if not connected:
             print(f"  ❌ Connection failed (client.is_connected() is {connected})")
             sys.exit(1)

        # 5. Check Authorization
        authorized = await client.is_user_authorized()
        print(f"  ✅ Telegram client connected, authorized = {authorized}")
        
        if not authorized:
            print("  ⚠ Session is not authorized. Need to re-login / refresh session_string.")
            # We can't proceed with other tests if not authorized
        else:
             # 6. Send 'Self' Test Message
            print("  📨 Sending test message to 'Saved Messages' (me)...")
            try:
                me = await client.get_me()
                print(f"    User: {me.first_name} (ID: {me.id})")
                await client.send_message('me', f"Telethon Auth Test: {item.get('phone')}\\nProxy: {p_host}")
                print("    ✉️  Test message sent to Saved Messages (me)")
            except Exception as e:
                print(f"    ⚠️ Failed to send test message: {e}")

            # 7. Optional Comment Check
            if channel_url and post_id:
                print(f"\n  📝 Checking Commenting Capability on {channel_url} (Post {post_id})...")
                try:
                    # Resolve Channel
                    entity = await client.get_entity(channel_url)
                    print(f"    ✓ Channel Resolved: {entity.title} (ID: {entity.id})")
                    
                    # Check Message
                    msgs = await client.get_messages(entity, ids=post_id)
                    if not msgs:
                        print(f"    ❌ MSG_NOT_FOUND: Post {post_id} does not exist in channel")
                    else:
                        print("    ✓ Post found")
                        
                        # Check Linked Discussion
                        full_channel = await client(GetFullChannelRequest(entity))
                        linked_id = full_channel.full_chat.linked_chat_id
                        
                        if linked_id:
                            print(f"    🔗 Linked Chat ID: {linked_id}")
                            try:
                                discussion_entity = await client.get_entity(linked_id)
                                print(f"    ✓ Discussion Group Resolved: {discussion_entity.title}")
                                
                                # Try Join
                                try:
                                    await client(JoinChannelRequest(discussion_entity))
                                    print("    ✓ Joined discussion group")
                                except Exception as e:
                                    print(f"    ⚠ Join Warning: {e}")

                            except Exception as e:
                                print(f"    ⚠ Failed to resolve discussion group: {e}")
                            
                            # Try Send (Dry Run / or Actual Test?) 
                            # User said "log RPC error (no retries)". Implying we SHOULD try to send.
                            print("    try sending 'test comment'...")
                            try:
                                await client.send_message(entity, "test comment (debug script)", comment_to=post_id)
                                print("    ✅ Comment Sent Successfully!")
                            except Exception as e:
                                print(f"    ❌ Comment Failed: {e}")
                        else:
                            print("    ℹ No linked discussion group found for this channel.")
                            
                except Exception as e:
                    print(f"    ❌ Channel/Post Check Error: {e}")

    except Exception as e:
        print(f"  ❌ Client Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
            print("\n  🔌 Disconnected")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check Telegram Account Proxy & Connectivity")
    parser.add_argument("--account-id", type=int, required=True, help="Directus Account ID")
    parser.add_argument("--channel-url", type=str, help="Optional: Channel URL to test commenting")
    parser.add_argument("--post-id", type=int, help="Optional: Post ID to test commenting")
    
    args = parser.parse_args()
    
    if (args.channel_url and not args.post_id) or (args.post_id and not args.channel_url):
        print("Error: Both --channel-url and --post-id must be provided together.")
        sys.exit(1)

    print("-" * 60)
    print("ℹ HINT: If you get connection errors to Directus, make sure to run this inside Docker:")
    print(f"  docker compose exec backend python -m backend.scripts.check_telegram_account --account-id {args.account_id}")
    print("-" * 60)
    
    asyncio.run(check_account(args.account_id, args.channel_url, args.post_id))
