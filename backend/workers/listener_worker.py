"""
Telegram Listener Worker

This worker monitors Telegram channels and saves parsed messages to Directus.
It uses accounts with work_mode='listener' to fetch messages from active channels.
"""

import asyncio
import os
import sys
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

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

# Initialize Directus client
directus = DirectusClient()

# Configuration
CHECK_INTERVAL = 300  # 5 minutes between cycles
CHANNEL_DELAY_MIN = 2  # Minimum delay between channels (seconds)
CHANNEL_DELAY_MAX = 5  # Maximum delay between channels (seconds)
MESSAGES_PER_FETCH = 100  # Number of messages to fetch per channel


async def check_collections():
    """
    Check if required collections exist in Directus.
    Prints warnings if collections are missing.
    """
    print("Checking Directus collections...")
    
    try:
        # Try to fetch from collections to verify they exist
        await directus.client.get("/items/channels", params={"limit": 1})
        print("✓ Collection 'channels' exists")
    except Exception as e:
        print(f"⚠ WARNING: Collection 'channels' may not exist: {e}")
        print("  Required fields: id, url, status, last_parsed_id, user_created")
    
    try:
        await directus.client.get("/items/parsed_posts", params={"limit": 1})
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
        "fields": "id,url,last_parsed_id,user_created",
        "limit": -1
    }
    
    if user_id:
        params["filter[user_created][_eq]"] = user_id
    
    try:
        response = await directus.client.get("/items/channels", params=params)
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
        "fields": "id,phone,session_string,api_id,api_hash,user_created",
        "limit": 1
    }
    
    if user_id:
        params["filter[user_created][_eq]"] = user_id
    
    try:
        response = await directus.client.get("/items/accounts", params=params)
        accounts = response.json().get('data', [])
        
        if accounts:
            print(f"Using listener account: {accounts[0]['phone']}")
            return accounts[0]
        else:
            print("⚠ No available listener accounts found")
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
        print(f"Updated channel {channel_id} last_parsed_id to: {last_id}")
    except Exception as e:
        print(f"Error updating last_parsed_id: {e}")


async def save_parsed_post(channel_url: str, post_id: int, text: str, user_created: str):
    """Save a parsed post to Directus."""
    try:
        post_data = {
            "channel_url": channel_url,
            "post_id": post_id,
            "text": text or "",
            "user_created": user_created
        }
        
        await directus.create_item("parsed_posts", post_data)
    except Exception as e:
        print(f"Error saving parsed post {post_id}: {e}")


async def parse_channel(client: TelegramClient, channel: Dict):
    """
    Parse messages from a single Telegram channel.
    
    Args:
        client: Connected Telethon client
        channel: Channel dictionary from Directus
    """
    channel_url = channel['url']
    channel_id = channel['id']
    last_parsed_id = channel.get('last_parsed_id', 0) or 0
    user_created = channel.get('user_created')
    
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
        for msg in messages:
            await save_parsed_post(
                channel_url=channel_url,
                post_id=msg.id,
                text=msg.text,
                user_created=user_created
            )
            new_last_id = max(new_last_id, msg.id)
        
        # Update last_parsed_id
        await update_last_parsed_id(channel_id, new_last_id)
        print(f"   ✓ Saved {len(messages)} messages, new last_id: {new_last_id}")
        
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


async def listener_cycle():
    """
    Main listener cycle:
    1. Fetch active channels
    2. Fetch listener account
    3. Connect to Telegram
    4. Parse each channel
    """
    print("\n" + "="*60)
    print(f"🔄 Starting listener cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Fetch channels
    channels = await get_active_channels()
    
    if not channels:
        print("No active channels to parse")
        return
    
    # Fetch listener account
    account = await get_listener_account()
    
    if not account:
        print("❌ No listener account available, skipping cycle")
        return
    
    # Connect to Telegram
    client = None
    try:
        # Use session string if available
        session_string = account.get('session_string')
        api_id = int(account['api_id']) if account.get('api_id') else 2040
        api_hash = account.get('api_hash') or "b18441a1ff607e10a989891a5462e627"
        
        if session_string:
            from telethon.sessions import StringSession
            client = TelegramClient(
                StringSession(session_string),
                api_id,
                api_hash
            )
        else:
            print("⚠ Account has no session_string, cannot connect")
            return
        
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Account is not authorized")
            return
        
        print(f"✓ Connected to Telegram as {account['phone']}")
        
        # Parse each channel
        for i, channel in enumerate(channels, 1):
            print(f"\n[{i}/{len(channels)}]", end=" ")
            await parse_channel(client, channel)
            
            # Delay between channels (except last one)
            if i < len(channels):
                delay = random.uniform(CHANNEL_DELAY_MIN, CHANNEL_DELAY_MAX)
                print(f"   ⏱ Sleeping {delay:.1f}s before next channel...")
                await asyncio.sleep(delay)
        
        print(f"\n✓ Cycle completed, parsed {len(channels)} channels")
        
    except Exception as e:
        print(f"❌ Error in listener cycle: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if client:
            await client.disconnect()
            print("Disconnected from Telegram")


async def run_listener_worker():
    """Main worker loop."""
    print("🚀 Telegram Listener Worker starting...")
    print(f"   Check interval: {CHECK_INTERVAL}s")
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
    
    # Main loop
    while True:
        try:
            await listener_cycle()
        except Exception as e:
            print(f"❌ Unexpected error in main loop: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n💤 Sleeping for {CHECK_INTERVAL}s until next cycle...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_listener_worker())
