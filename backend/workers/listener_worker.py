"""
Telegram Listener Worker

This worker monitors Telegram channels and saves parsed messages to Directus.
It uses accounts with work_mode='listener' to fetch messages from active channels.
Refactored to use TaskQueueManager architecture.
"""

import asyncio
import os
import sys
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    ChannelBannedError,
    UsernameInvalidError,
    UsernameNotOccupiedError
)
from telethon.tl.types import Channel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient
from backend.services.task_queue_manager import TaskQueueManager

# Configuration
CHANNEL_DELAY_MIN = 2  # Minimum delay between channels (seconds)
CHANNEL_DELAY_MAX = 5  # Maximum delay between channels (seconds)
MESSAGES_PER_FETCH = 100  # Number of messages to fetch per channel


class TaskHandler:
    async def get_supported_task_types(self) -> List[str]:
        raise NotImplementedError
    
    async def process_task(self, task: Dict[str, Any]) -> bool:
        raise NotImplementedError


# Initialize Directus client
directus = DirectusClient()


async def check_collections():
    """
    Check if required collections exist in Directus.
    Prints warnings if collections are missing.
    """
    print("Checking Directus collections...")
    
    try:
        # Try to fetch from collections to verify they exist
        await directus.safe_get("/items/channels", params={"limit": 1})
        print("✓ Collection 'channels' exists")
    except Exception as e:
        print(f"⚠ WARNING: Collection 'channels' may not exist: {e}")
        print("  Required fields: id, url, status, last_parsed_id, user_created")
    
    try:
        await directus.safe_get("/items/parsed_posts", params={"limit": 1})
        print("✓ Collection 'parsed_posts' exists")
    except Exception as e:
        print(f"⚠ WARNING: Collection 'parsed_posts' may not exist: {e}")
        print("  Required fields: id, channel_url, post_id, text, date_created, user_created")


async def get_active_channels(user_id: Optional[str] = None) -> List[Dict]:
    """
    Fetch active channels from Directus.
    
    Args:
        user_id: Optional user ID for filtering (user isolation)
    
    Returns:
        List of active channel dictionaries
    """
    params = {
        "filter[status][_eq]": "active",
        "filter[url][_nnull]": "true",
        "fields": "id,url,last_parsed_id,user_created",
        "limit": -1
    }
    
    if user_id:
        params["filter[user_created][_eq]"] = user_id
    
    try:
        response = await directus.safe_get("/items/channels", params=params)
        channels = response.json().get('data', [])
        print(f"Found {len(channels)} active channels")
        return channels
    except Exception as e:
        print(f"Error fetching channels: {e}")
        return []


async def get_listener_account(user_id: Optional[str] = None) -> Optional[Dict]:
    """
    Fetch one available listener account from Directus.
    
    Args:
        user_id: Optional user ID for filtering (user isolation)
    
    Returns:
        Account dictionary or None
    """
    params = {
        "filter[status][_eq]": "active",
        "filter[work_mode][_eq]": "listener",
        "filter[session_string][_nnull]": "true",
        "filter[proxy_unavailable][_neq]": "true",
        "fields": "id,phone,session_string,api_id,api_hash,user_created,proxy_unavailable,proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type,proxy_id.username,proxy_id.password,proxy_id.status,proxy_id.assigned_to",
        "limit": 1
    }
    
    if user_id:
        params["filter[user_created][_eq]"] = user_id
    
    try:
        print("[DEBUG listener] get_listener_account params:", params)
        
        response = await directus.safe_get("/items/accounts", params=params)
        
        try:
            raw_text = response.text
        except Exception:
            raw_text = "<no text>"
            
        print(f"[DEBUG listener] get_listener_account status={response.status_code}")
        print(f"[DEBUG listener] get_listener_account raw response: {raw_text[:500]}")
        
        data = response.json()
        accounts = data.get('data', [])
        
        print(f"[DEBUG listener] get_listener_account parsed data count={len(accounts)}")
        
        if accounts:
            print(f"Using listener account: {accounts[0]['phone']}")
            return accounts[0]
        else:
            print("⚠ No available listener accounts found (data array empty)")
            return None
    except Exception as e:
        print(f"Error fetching listener account: {e}")
        return None


async def update_channel_status(channel_id: str, status: str):
    """Update channel status in Directus."""
    try:
        await directus.update_item("channels", channel_id, {"status": status})
        print(f"Updated channel {channel_id} status to: {status}")
    except Exception as e:
        print(f"Error updating channel status: {e}")


async def update_last_parsed_id(channel_id: str, last_id: int):
    """Update last_parsed_id for a channel in Directus."""
    try:
        await directus.update_item("channels", channel_id, {"last_parsed_id": last_id})
        # print(f"Updated channel {channel_id} last_parsed_id to: {last_id}")
    except Exception as e:
        print(f"Error updating last_parsed_id: {e}")


async def save_parsed_post(channel_url: str, post_id: int, text: str, user_created: str) -> bool:
    """Save a parsed post to Directus. Returns True if saved, False if duplicate/error."""
    try:
        # Idempotency check: see if it already exists
        params = {
            "filter[channel_url][_eq]": channel_url,
            "filter[post_id][_eq]": post_id,
            "fields": "id",
            "limit": 1
        }
        
        existing = await directus.safe_get("/items/parsed_posts", params=params)
        if existing.json().get('data'):
            # Already exists
            return False

        post_data = {
            "channel_url": channel_url,
            "post_id": post_id,
            "text": text or "",
            "status": "published",
            "user_created": user_created
        }
        
        await directus.create_item("parsed_posts", post_data)
        return True
    except Exception as e:
        print(f"Error saving parsed post {post_id}: {e}")
        return False


async def parse_channel(client: TelegramClient, task_payload: Dict):
    """
    Parse messages from a single Telegram channel.
    
    Args:
        client: Connected Telethon client
        task_payload: Task payload containing channel_url, channel_id, and last_parsed_id
    """
    channel_url = task_payload['channel_url']
    channel_id = task_payload['channel_id']
    last_parsed_id = task_payload.get('last_parsed_id', 0) or 0
    
    # For listener tasks, we'll fetch user_created from the channels table
    try:
        channel_info = await directus.get_item("channels", channel_id, params={"fields": "user_created"})
        user_created = channel_info.get('user_created') if channel_info else None
    except Exception as e:
        print(f"Error fetching channel info for {channel_id}: {e}")
        user_created = None
    
    print(f"\n📡 Parsing channel: {channel_url}")
    print(f"   Last parsed ID: {last_parsed_id}")
    
    try:
        # Resolve channel entity
        entity = await client.get_entity(channel_url)
        
        if not isinstance(entity, Channel):
            print(f"⚠ {channel_url} is not a channel, skipping")
            return
        
        # Fetch new messages
        messages = []
        async for message in client.iter_messages(
            entity,
            limit=MESSAGES_PER_FETCH,
            min_id=last_parsed_id
        ):
            if message.text:
                messages.append(message)
        
        if not messages:
            print(f"   No new messages")
            return
        
        print(f"   Found {len(messages)} new messages")
        
        # Save messages to Directus (newest first, so reverse)
        messages.reverse()
        
        new_last_id = last_parsed_id
        saved_count = 0
        
        for msg in messages:
            is_saved = await save_parsed_post(
                channel_url=channel_url,
                post_id=msg.id,
                text=msg.text,
                user_created=user_created
            )
            if is_saved:
                saved_count += 1
            
            new_last_id = max(new_last_id, msg.id)
        
        # Update last_parsed_id if we have new messages (even if they were all duplicates, update usage cursor)
        # But per requirements: "если найден хотя бы один новый, обновить channels.last_parsed_id"
        # We'll update it to the max id seen to keep things moving forward.
        if new_last_id > last_parsed_id:
            await update_last_parsed_id(channel_id, new_last_id)
            
        if saved_count > 0:
            print(f"   ✓ Saved {saved_count} new posts for channel {channel_url}")
        else:
            print(f"   No new posts saved (duplicates or skipped)")
        
    except (ChannelPrivateError, ChannelBannedError) as e:
        print(f"   ✗ Channel is private or banned: {e}")
        await update_channel_status(channel_id, "error")
    
    except (UsernameInvalidError, UsernameNotOccupiedError) as e:
        print(f"   ✗ Invalid channel URL: {e}")
        await update_channel_status(channel_id, "error")
    
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"   ⏳ FloodWait: need to wait {wait_seconds} seconds")
        await asyncio.sleep(wait_seconds)
    
    except Exception as e:
        print(f"   ✗ Error parsing channel: {e}")


class ListenerTaskHandler(TaskHandler):
    async def get_supported_task_types(self) -> List[str]:
        return ['fetch_posts']

    async def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a fetch_posts task.
        
        Args:
            task: Task dictionary with type 'fetch_posts' and payload
            
        Returns:
            True if task was processed successfully, False otherwise
        """
        print(f"\n📡 Processing fetch_posts task: {task['id']}")
        
        task_payload = task['payload']
        channel_url = task_payload['channel_url']
        channel_id = task_payload['channel_id']
        
        # Get a listener account
        account = await get_listener_account()
        
        if not account:
            error_msg = f"No available listener account for task {task['id']}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)  # This will cause the task to be retried
        
        print(f"Using listener account: {account['phone']}")
        
        # Guard: Check for proxy unavailability
        if account.get('proxy_unavailable'):
            error_msg = f"Listener account {account['phone']} has proxy_unavailable=True"
            print(f"⚠ {error_msg}")
            raise Exception(error_msg)  # This will cause the task to be retried
        
        client = None
        try:
            # Create client via factory (with mandatory proxy)
            try:
                from backend.services.telegram_client_factory import get_client_for_account, format_proxy
                
                client = await get_client_for_account(account, directus)
                
                # Safe logging before connect (no credentials)
                proxy = account.get('proxy_id')
                if proxy:
                    print(f"[TG] connect account_id={account['id']} phone={account['phone']} via {format_proxy(proxy)}")
                else:
                    print(f"[TG] connect account_id={account['id']} phone={account['phone']} - no proxy info")
                    
            except (ValueError, RuntimeError) as e:
                # Factory error: missing proxy, invalid proxy status, etc.
                error_msg = f"Cannot create Telegram client for account {account['id']}: {e}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            await client.connect()
            
            if not await client.is_user_authorized():
                error_msg = f"Account {account['phone']} is not authorized"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            print(f"✓ Connected to Telegram as {account['phone']}")
            
            # Call parse_channel with task payload
            await parse_channel(client, task_payload)
            
            print(f"✓ Task {task['id']} completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error processing task {task['id']}: {e}")
            import traceback
            traceback.print_exc()
            raise  # Re-raise to let the task manager handle retries
        
        finally:
            if client:
                await client.disconnect()
                print("Disconnected from Telegram")


async def run_listener_worker():
    """Main worker loop using TaskQueueManager."""
    print("🚀 Telegram Listener Worker starting with TaskQueueManager...")
    print(f"   Messages per fetch: {MESSAGES_PER_FETCH}")
    
    # Login to Directus
    try:
        await directus.login()
        print("✓ Logged in to Directus")
    except Exception as e:
        print(f"❌ Failed to login to Directus: {e}")
        return
    
    # Check collections
    await check_collections()
    
    # Initialize TaskQueueManager with ListenerTaskHandler
    task_queue_manager = TaskQueueManager()
    listener_handler = ListenerTaskHandler()
    
    print("Starting TaskQueueManager with ListenerTaskHandler...")
    
    # Run the TaskQueueManager (this handles the main loop)
    worker_id = 'listener-worker'
    task_types = await listener_handler.get_supported_task_types()
    
    print(f"Listening for tasks: {task_types}, worker_id: {worker_id}")
    
    while True:
        try:
            # Claim a task from the queue
            task = await task_queue_manager.claim_task(worker_id, task_types)
            
            if task:
                print(f"Claimed task {task['id']} of type {task['type']}")
                try:
                    success = await listener_handler.process_task(task)
                    if success:
                        await task_queue_manager.complete_task(task['id'])
                    else:
                        await task_queue_manager.fail_task(task['id'], "Task processing failed")
                except Exception as e:
                    await task_queue_manager.fail_task(task['id'], str(e))
            else:
                # No tasks available, wait before checking again
                await asyncio.sleep(5)  # Check for new tasks every 5 seconds
                
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)  # Wait before continuing


if __name__ == "__main__":
    asyncio.run(run_listener_worker())
