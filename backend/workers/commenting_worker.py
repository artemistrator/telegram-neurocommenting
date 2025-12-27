"""
Telegram Commenting Worker

This worker executes commenting tasks from the `comment_queue`.
It acts as a dumb executor:
1. Picks up 'pending' tasks.
2. Uses the specified account.
3. Checks daily limits for safety.
4. Waits for the required delay.
5. Posts the comment to Telegram utilizing `comment_to` logic (discussion groups).
6. Updates status to 'posted' or 'failed'.
"""

import asyncio
import os
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    ChannelBannedError,
    MessageIdInvalidError,
    UserAlreadyParticipantError
)
from telethon.tl.functions.channels import JoinChannelRequest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient

# Initialize clients
directus = DirectusClient()

# Configuration
CHECK_INTERVAL = 30  # Check queue every 30 seconds (executor should be responsive)
DEFAULT_MIN_DELAY = 30
DEFAULT_MAX_DELAY = 60
DRY_RUN = False  # Set via env var if needed

async def check_collections():
    """Verify required collections exist."""
    print("Checking Directus collections...")
    required = ["comment_queue", "accounts"]
    for col in required:
        try:
            await directus.safe_get(f"/items/{col}", params={"limit": 1})
        except Exception as e:
            print(f"⚠ WARNING: Collection '{col}' may not exist: {e}")

async def get_pending_tasks(limit: int = 10) -> List[Dict]:
    """Fetch pending tasks from comment_queue."""
    params = {
        "filter[status][_eq]": "pending",
        "fields": "id,account_id,parsed_post_id,channel_url,post_id,generated_comment",
        "limit": limit,
        "sort": "id"  # Oldest first
    }
    try:
        response = await directus.safe_get("/items/comment_queue", params=params)
        return response.json().get('data', [])
    except Exception as e:
        print(f"Error fetching pending tasks: {e}")
        return []


async def claim_task(task_id: int) -> bool:
    """Claim a task by updating its status to processing, preventing other workers from picking it up."""
    try:
        await directus.update_item("comment_queue", task_id, {"status": "processing"})
        return True
    except Exception as e:
        print(f"  ⚠ Failed to claim task {task_id}: {e}")
        return False


async def get_account_for_task(account_id: int) -> Optional[Dict]:
    """Fetch specific account details."""
    params = {
        "filter[id][_eq]": account_id,
        "filter[status][_eq]": "active",
        "filter[work_mode][_eq]": "commenter",
        "filter[session_string][_nnull]": "true",
        "filter[proxy_unavailable][_neq]": "true",
        "fields": "id,phone,session_string,api_id,api_hash,user_created,max_comments_per_day,min_delay_between_comments,max_delay_between_comments,proxy_unavailable,proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type,proxy_id.username,proxy_id.password,proxy_id.status,proxy_id.assigned_to",
        "limit": 1
    }
    try:
        response = await directus.safe_get("/items/accounts", params=params)
        data = response.json().get('data', [])
        return data[0] if data else None
    except Exception as e:
        print(f"Error fetching account {account_id}: {e}")
        return None

async def check_daily_limit(account_id: int, max_per_day: Optional[int]) -> bool:
    """Check if account has reached daily limit."""
    if not max_per_day or max_per_day <= 0:
        return True # No limit

    yesterday = datetime.utcnow() - timedelta(days=1)
    
    params = {
        "filter[account_id][_eq]": account_id,
        "filter[status][_eq]": "posted",
        "filter[posted_at][_gte]": yesterday.isoformat(),
        "aggregate[count]": "id"
    }
    
    try:
        response = await directus.safe_get("/items/comment_queue", params=params)
        data = response.json()
        count = 0
        if 'data' in data and data['data']:
            count = int(data['data'][0].get('count', 0))
        
        if count >= max_per_day:
            print(f"  ⚠ Daily limit reached for account {account_id} ({count}/{max_per_day})")
            return False
        return True
    except Exception as e:
        print(f"Error checking limit: {e}")
        return True 

async def update_task_status(task_id: int, status: str, error_msg: Optional[str] = None):
    """Update task status in Directus."""
    payload = {
        "status": status,
        "posted_at": datetime.utcnow().isoformat() if status == "posted" else None
    }
    if error_msg:
        payload["error_message"] = str(error_msg)[:1024]
    
    try:
        await directus.update_item("comment_queue", task_id, payload)
    except Exception as e:
        print(f"  ⚠ Failed to update task {task_id}: {e}")

async def ensure_joined(client: TelegramClient, entity):
    """
    Ensure the client is joined to the channel/group.
    Required to comment/discuss in many channels.
    """
    try:
        await client(JoinChannelRequest(entity))
        print("    ✓ Joined (or already joined) channel/group")
    except UserAlreadyParticipantError:
        print("    ✓ Already a participant")
    except Exception as e:
        print(f"    ⚠ Join attempt failed: {e} (will try to comment anyway)")

from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetDiscussionMessageRequest

async def process_task(task: Dict):
    """Execute a single commenting task."""
    task_id = task['id']
    account_id = task['account_id']
    channel_url = task['channel_url']
    post_id = task['post_id']
    comment_text = task['generated_comment']

    print(f"\n📋 Processing Task #{task_id} (Post {post_id} in {channel_url})")

    # Claim the task first by updating status to "processing" to prevent duplicate processing
    if not await claim_task(task_id):
        print(f"  ❌ Failed to claim task {task_id}, skipping...")
        return

    # 1. Get Account
    account = await get_account_for_task(account_id)
    if not account:
        print(f"  ❌ Account {account_id} not available or invalid")
        await update_task_status(task_id, "failed", "Account not available/active")
        return

    print(f"  👤 Account: {account.get('phone')} (ID: {account_id})")

    # 2. Check Limits
    max_daily = account.get('max_comments_per_day')
    if not await check_daily_limit(account_id, max_daily):
        await update_task_status(task_id, "skipped", "Daily limit reached")
        return

    # 3. Calculate Delay
    min_delay = account.get('min_delay_between_comments') or DEFAULT_MIN_DELAY
    max_delay = account.get('max_delay_between_comments') or DEFAULT_MAX_DELAY
    
    if min_delay < 1: min_delay = 1
    if max_delay < min_delay: max_delay = min_delay + 5

    delay = random.uniform(min_delay, max_delay)
    print(f"  ⏱ Sleeping {delay:.1f}s...")
    if not DRY_RUN:
        await asyncio.sleep(delay)

    # 4. Connect & Post
    client = None
    try:
        from backend.services.telegram_client_factory import get_client_for_account
        
        # Guard: Check for missing proxy_id BEFORE attempting to create client
        if not account.get('proxy_id'):
            print(f"  ❌ Cannot create Telegram client for account {account_id}: No proxy assigned")
            await update_task_status(task_id, "failed", "No proxy assigned to account")
            return
        
        client = await get_client_for_account(account, directus)
        await client.connect()
        
        if not await client.is_user_authorized():
            raise Exception("Account not authorized in Telegram")

        # Resolve entity
        print(f"  🔍 Resolving channel: {channel_url}")
        channel = await client.get_entity(channel_url)
        print(f"  ✓ Channel resolved: {channel.title} (ID: {channel.id})")

        if DRY_RUN:
             print(f"  [DRY RUN] Checks passed. Would post: {comment_text}")
             await update_task_status(task_id, "posted")
             return

        # -------------------------------------------------------------
        # A & B: Debug & Validate Message Existence
        # -------------------------------------------------------------
        msgs = await client.get_messages(channel, ids=post_id)
        if not msgs:
            print(f"  ❌ Message {post_id} not found in channel")
            await update_task_status(task_id, "failed", "MSG_NOT_FOUND_IN_CHANNEL")
            return
        
        msg = msgs # get_messages with ids=int returns the message object or None? No, list if iterable, single if single.
        # telethon get_messages(ids=123) returns the message object directly (or None) if ids is scalr.
        # But wait, documentation says "If a list of IDs is provided...". 
        # Let's double check telethon behavior usually. 
        # If I pass `ids=[1]`, it returns `[Message]`. If `ids=1`, it returns `Message`.
        # The prompt used `client.get_messages(channel, ids=post_id)`.
        
        # -------------------------------------------------------------
        # C: Check Discussion Capabilities
        # -------------------------------------------------------------
        # We try to get the discussion message. If it fails, comments are not enabled.
        print(f"  🔍 Checking discussion availability for msg {post_id}...")
        try:
            # check if we can get discussion details
            await client(GetDiscussionMessageRequest(peer=channel, msg_id=post_id))
        except (MessageIdInvalidError, Exception) as e:
             # MessageIdInvalidError here usually entails "no discussion linked" or "post not found" 
             # (but we already checked post found). So likely "no comment section".
             print(f"  ⚠ No discussion/comments available: {e}")
             await update_task_status(task_id, "skipped", "NO_DISCUSSION_FOR_MESSAGE")
             return

        # -------------------------------------------------------------
        # D: Join Linked Discussion Group (Explicitly)
        # -------------------------------------------------------------
        linked_group = None
        try:
            full_channel = await client(GetFullChannelRequest(channel))
            linked_chat_id = full_channel.full_chat.linked_chat_id
            
            if linked_chat_id:
                print(f"  🔗 Linked discussion group ID: {linked_chat_id}")
                linked_group = await client.get_entity(linked_chat_id)
                await ensure_joined(client, linked_group)
            else:
                print("  ℹ No linked chat ID found in full channel info")
        except Exception as e:
            print(f"  ⚠ Failed to resolve/join linked group: {e}")
            # We continue, because sometimes comment_to works even if we can't see the group explicitly (rare but possible)
            # OR we might rely on fallback strategy later which might also fail, but we try.

        # -------------------------------------------------------------
        # E: Send Comment (Strategy 1 + Fallback)
        # -------------------------------------------------------------
        print(f"  Attempting comment_to post_id={post_id}...")
        try:
            # Strategy 1: Standard comment_to
            await client.send_message(channel, comment_text, comment_to=post_id)
            print(f"  ✅ Comment posted successfully (via comment_to)")
            
        except MessageIdInvalidError:
            print("  ⚠ 'comment_to' failed (MsgIdInvalidError). Attempting fallback...")
            
            # Strategy 2: Fallback - Get discussion message and reply there
            try:
                discussion_resp = await client(GetDiscussionMessageRequest(peer=channel, msg_id=post_id))
                # The response contains the discussion message in .messages
                # discussion_resp.messages[0] is the "thread starter" in the group.
                # discussion_resp.chats has the group info.
                
                if not discussion_resp.messages:
                    raise Exception("No discussion message returned in fallback")
                    
                target_msg = discussion_resp.messages[0]
                target_peer = discussion_resp.chats[0] # The group
                
                print(f"  Fallback: Replying to msg {target_msg.id} in group {target_peer.id}...")
                await client.send_message(target_peer, comment_text, reply_to=target_msg.id)
                print(f"  ✅ Comment posted successfully (via fallback)")
                
            except Exception as fallback_e:
                print(f"  ❌ Fallback failed: {fallback_e}")
                await update_task_status(task_id, "failed", "DISCUSSION_SEND_FAILED")
                return

        await update_task_status(task_id, "posted")

    except Exception as e:
        print(f"  ❌ Posting error: {e}")
        await update_task_status(task_id, "failed", str(e))
    finally:
        if client:
            await client.disconnect()

async def cycle():
    print("\n" + "="*60)
    print(f"🔄 Starting execution cycle at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*60)

    tasks = await get_pending_tasks()
    if not tasks:
        print("No pending comment tasks.")
        return

    print(f"Found {len(tasks)} pending tasks.")

    for task in tasks:
        await process_task(task)

async def run_worker():
    print("🚀 Commenting Executor Worker starting (Discussion Group Support)...")
    try:
        await directus.login()
        print("✓ Logged in to Directus")
    except Exception as e:
        print(f"❌ Directus Login Failed: {e}")
        return

    await check_collections()

    while True:
        try:
            await cycle()
        except Exception as e:
            print(f"❌ Error in executor cycle: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n💤 Sleeping for {CHECK_INTERVAL}s...")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(run_worker())