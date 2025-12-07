"""
Telegram Commenting Worker

This worker automatically posts AI-generated comments to Telegram channels.
It uses accounts with work_mode='commenter' and filters posts through AI classification.
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
    MessageIdInvalidError
)
from telethon.sessions import StringSession

import openai

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient

# Initialize clients
directus = DirectusClient()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuration
CHECK_INTERVAL = 300  # 5 minutes between cycles
COMMENT_DELAY_MIN = 60  # Minimum delay between comments (seconds)
COMMENT_DELAY_MAX = 180  # Maximum delay between comments (seconds)
DRY_RUN = True

async def check_collections():
    """
    Check if required collections exist in Directus.
    Prints warnings if collections are missing.
    """
    print("Checking Directus collections...")
    
    collections = [
        "parsed_posts",
        "comment_queue",
        "accounts",
        "commenting_profiles"
    ]
    
    for collection in collections:
        try:
            await directus.client.get(f"/items/{collection}", params={"limit": 1})
            print(f"✓ Collection '{collection}' exists")
        except Exception as e:
            print(f"⚠ WARNING: Collection '{collection}' may not exist: {e}")


async def get_uncommented_posts(user_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """
    Fetch posts that haven't been commented on yet.
    
    Args:
        user_id: Optional user ID for filtering (user isolation)
        limit: Maximum number of posts to fetch
    
    Returns:
        List of parsed post dictionaries
    """
    params = {
        "fields": "id,channel_url,post_id,text,user_created",
        "limit": limit,
        "sort": "-id"  # Newest first
    }
    
    if user_id:
        params["filter[user_created][_eq]"] = user_id
    
    try:
        # Get all posts
        response = await directus.client.get("/items/parsed_posts", params=params)
        all_posts = response.json().get('data', [])
        
        if not all_posts:
            return []
        
        # Get all comment queue entries to filter out already commented posts
        queue_params = {
            "fields": "parsed_post_id",
            "limit": -1
        }
        
        if user_id:
            queue_params["filter[user_created][_eq]"] = user_id
        
        queue_response = await directus.client.get("/items/comment_queue", params=queue_params)
        commented_post_ids = {
            item['parsed_post_id'] 
            for item in queue_response.json().get('data', [])
            if item.get('parsed_post_id')
        }
        
        # Filter out already commented posts
        uncommented = [
            post for post in all_posts 
            if post['id'] not in commented_post_ids
        ]
        
        print(f"Found {len(uncommented)} uncommented posts (out of {len(all_posts)} total)")
        return uncommented
        
    except Exception as e:
        print(f"Error fetching uncommented posts: {e}")
        return []


async def get_commenter_account(user_id: Optional[str] = None) -> Optional[Dict]:
    """
    Fetch one available commenter account with active commenting profile.
    
    Args:
        user_id: Optional user ID for filtering (user isolation)
    
    Returns:
        Account dictionary with profile data or None
    """
    params = {
        "filter[status][_eq]": "active",
        "filter[work_mode][_eq]": "commenter",
        "filter[commenting_profile_id][_nnull]": "true",
        "fields": "id,phone,session_string,api_id,api_hash,user_created,commenting_profile_id.*",
        "limit": 1
    }
    
    if user_id:
        params["filter[user_created][_eq]"] = user_id
    
    try:
        response = await directus.client.get("/items/accounts", params=params)
        accounts = response.json().get('data', [])
        
        if accounts:
            account = accounts[0]
            profile = account.get('commenting_profile_id')
            
            if not profile:
                print("⚠ Account has no active commenting profile")
                return None
            
            print(f"Using commenter account: {account['phone']}")
            print(f"  Profile: {profile.get('name', 'Unnamed')}")
            print(f"  Filter mode: {profile.get('filter_mode', 'none')}")
            print(f"  Max comments/day: {profile.get('max_comments_per_day', 'unlimited')}")
            
            return account
        else:
            print("⚠ No available commenter accounts found")
            return None
            
    except Exception as e:
        print(f"Error fetching commenter account: {e}")
        return None


async def check_daily_limit(account_id: str, max_per_day: Optional[int]) -> bool:
    """
    Check if account has reached daily comment limit.
    
    Args:
        account_id: Account ID
        max_per_day: Maximum comments per day (None = unlimited)
    
    Returns:
        True if can comment, False if limit reached
    """
    if not max_per_day:
        return True
    
    try:
        # Get today's date range
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count comments posted today
        params = {
            "filter[account_id][_eq]": account_id,
            "filter[status][_eq]": "posted",
            "filter[posted_at][_gte]": today_start.isoformat(),
            "aggregate[count]": "id"
        }
        
        response = await directus.client.get("/items/comment_queue", params=params)
        data = response.json()
        
        # Extract count from aggregation
        count = 0
        if 'data' in data and data['data']:
            count = len(data['data'])
        
        print(f"  Daily comments: {count}/{max_per_day}")
        
        return count < max_per_day
        
    except Exception as e:
        print(f"Error checking daily limit: {e}")
        return True  # Allow on error


async def filter_post_with_ai(post_text: str, profile: Dict) -> bool:
    """
    Filter post through AI classification.
    
    Args:
        post_text: Text of the post
        profile: Commenting profile with filter settings
    
    Returns:
        True if post should be commented, False otherwise
    """
    filter_mode = profile.get('filter_mode', 'none')
    
    if filter_mode == 'none':
        return True
    
    if filter_mode == 'keywords':
        keywords = profile.get('filter_keywords', [])
        
        # Handle both list and string formats
        if isinstance(keywords, str):
            keyword_list = [k.strip().lower() for k in keywords.split(',')]
        elif isinstance(keywords, list):
            keyword_list = [k.strip().lower() for k in keywords]
        else:
            return True
        
        if not keyword_list:
            return True
        
        post_lower = post_text.lower()
        
        for keyword in keyword_list:
            if keyword in post_lower:
                print(f"  ✓ Matched keyword: '{keyword}'")
                return True
        
        print(f"  ⊘ No matching keywords")
        return False
    
    if filter_mode == 'ai_classification':
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=openai.api_key)
            
            system_prompt = """You are a content filter. Analyze the post and determine if it's relevant for commenting.
Reply ONLY with YES or NO, nothing else."""
            
            user_prompt = f"""Post text:
{post_text}

Filter criteria: {profile.get('filter_keywords', 'general relevance')}

Should this post be commented on?"""
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=10
            )
            
            decision = response.choices[0].message.content.strip().upper()
            should_comment = decision == "YES"
            
            print(f"  AI filter: {decision} → {'PASS' if should_comment else 'SKIP'}")
            return should_comment
            
        except Exception as e:
            print(f"  AI filter error: {e}, defaulting to SKIP")
            return False
    
    return True


async def generate_comment(post_text: str, profile: Dict) -> Optional[str]:
    """Generate comment using OpenAI GPT-4o."""
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=openai.api_key)
        
        system_prompt = profile.get('system_prompt', 'You are a helpful commenter.')
        max_words = profile.get('max_words', 50)
        
        user_prompt = f"""Post:
{post_text}

Generate a relevant comment (max {max_words} words)."""
        
        response = await client.chat.completions.create(  # ← НОВЫЙ СИНТАКСИС
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=max_words * 2
        )
        
        comment = response.choices[0].message.content.strip()
        print(f"  Generated comment: {comment[:100]}...")
        return comment

        
    except Exception as e:
        print(f"  Error generating comment: {e}")
        return None


async def post_comment_to_telegram(
    client: TelegramClient,
    channel_url: str,
    post_id: int,
    comment_text: str
) -> tuple[bool, Optional[str]]:
    """
    Post comment to Telegram channel.
    
    Args:
        client: Connected Telethon client
        channel_url: Channel URL
        post_id: Post ID to reply to
        comment_text: Comment text
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # DRY RUN MODE - Skip actual posting
        if DRY_RUN:
            print(f"  💬 [DRY RUN] Would post comment: {comment_text[:100]}...")
            print(f"     Channel: {channel_url}, Post ID: {post_id}")
            return True, None
        
        # Real posting
        entity = await client.get_entity(channel_url)
        
        # Send comment as reply to the post
        await client.send_message(
            entity,
            comment_text,
            reply_to=post_id
        )
        
        print(f"  ✓ Comment posted successfully")
        return True, None
        
    except FloodWaitError as e:
        wait_seconds = e.seconds
        error_msg = f"FloodWait: {wait_seconds}s"
        print(f"  ⏳ {error_msg}")
        return False, error_msg
    
    except (ChannelPrivateError, ChannelBannedError) as e:
        error_msg = f"Channel access error: {str(e)}"
        print(f"  ✗ {error_msg}")
        return False, error_msg
    
    except MessageIdInvalidError as e:
        error_msg = f"Invalid message ID: {str(e)}"
        print(f"  ✗ {error_msg}")
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"  ✗ {error_msg}")
        return False, error_msg


async def process_post(
    client: TelegramClient,
    post: Dict,
    account: Dict,
    profile: Dict
) -> bool:
    """
    Process a single post: filter, generate comment, post to Telegram.
    
    Args:
        client: Connected Telethon client
        post: Parsed post dictionary
        account: Account dictionary
        profile: Commenting profile dictionary
    
    Returns:
        True if comment was posted successfully
    """
    post_id = post['id']
    channel_url = post['channel_url']
    telegram_post_id = post['post_id']
    post_text = post['text']
    user_created = post.get('user_created')
    
    print(f"\n📝 Processing post {post_id} from {channel_url}")
    print(f"   Telegram post ID: {telegram_post_id}")
    
    # Check daily limit
    max_per_day = profile.get('max_comments_per_day')
    if not await check_daily_limit(account['id'], max_per_day):
        print(f"  ⚠ Daily limit reached ({max_per_day}), skipping")
        return False
    
    # Apply warmup mode if enabled
    if profile.get('warmup_mode'):
        warmup_max = profile.get('warmup_max_per_day', 5)
        if not await check_daily_limit(account['id'], warmup_max):
            print(f"  ⚠ Warmup limit reached ({warmup_max}), skipping")
            return False
    
    # Filter post
    if not await filter_post_with_ai(post_text, profile):
        print(f"  ⊘ Post filtered out, skipping")
        return False
    
    # Generate comment
    comment_text = await generate_comment(post_text, profile)
    if not comment_text:
        print(f"  ✗ Failed to generate comment, skipping")
        return False
    
    # Create queue entry (pending)
    try:
        queue_data = {
            "parsed_post_id": post_id,
            "account_id": account['id'],
            "comment_text": comment_text,
            "status": "pending",
            "user_created": user_created
        }
        
        response = await directus.client.post("/items/comment_queue", json=queue_data)
        queue_entry = response.json().get('data')
        queue_id = queue_entry['id']
        print(f"  ✓ Created queue entry {queue_id}")
        
    except Exception as e:
        print(f"  ✗ Error creating queue entry: {e}")
        return False
    
    # Post to Telegram
    success, error_msg = await post_comment_to_telegram(
        client,
        channel_url,
        telegram_post_id,
        comment_text
    )
    
    # Update queue entry
    try:
        if success:
            await directus.client.patch(f"/items/comment_queue/{queue_id}", json={
                "status": "posted",
                "posted_at": datetime.now().isoformat()
            })
        else:
            await directus.client.patch(f"/items/comment_queue/{queue_id}", json={
                "status": "failed",
                "error_message": error_msg
            })
    except Exception as e:
        print(f"  ⚠ Error updating queue entry: {e}")
    
    return success


async def commenting_cycle():
    """
    Main commenting cycle:
    1. Fetch uncommented posts
    2. Fetch commenter account with profile
    3. Connect to Telegram
    4. Process each post (filter, generate, comment)
    """
    print("\n" + "="*60)
    print(f"🔄 Starting commenting cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Fetch uncommented posts
    posts = await get_uncommented_posts()
    
    if not posts:
        print("No uncommented posts to process")
        return
    
    # Fetch commenter account
    account = await get_commenter_account()
    
    if not account:
        print("❌ No commenter account available, skipping cycle")
        return
    
    profile = account.get('commenting_profile_id')
    if not profile:
        print("❌ Account has no commenting profile, skipping cycle")
        return
    
    # Connect to Telegram
    client = None
    try:
        session_string = account.get('session_string')
        api_id = int(account['api_id']) if account.get('api_id') else 2040
        api_hash = account.get('api_hash') or "b18441a1ff607e10a989891a5462e627"
        
        if not session_string:
            print("⚠ Account has no session_string, cannot connect")
            return
        
        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash
        )
        
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Account is not authorized")
            return
        
        print(f"✓ Connected to Telegram as {account['phone']}")
        
        # Process posts
        comments_posted = 0
        max_per_day = profile.get('max_comments_per_day')
        
        for i, post in enumerate(posts, 1):
            print(f"\n[{i}/{len(posts)}]", end=" ")
            
            # Check if we've hit daily limit
            if max_per_day and comments_posted >= max_per_day:
                print(f"\n⚠ Reached daily limit ({max_per_day}), stopping")
                break
            
            # Process post
            success = await process_post(client, post, account, profile)
            
            if success:
                comments_posted += 1
                
                # Delay between comments
                min_delay = profile.get('min_delay', COMMENT_DELAY_MIN)
                max_delay = profile.get('max_delay', COMMENT_DELAY_MAX)
                delay = random.randint(min_delay, max_delay)
                
                print(f"   ⏱ Sleeping {delay}s before next comment...")
                await asyncio.sleep(delay)
        
        print(f"\n✓ Cycle completed, posted {comments_posted} comments")
        
    except Exception as e:
        print(f"❌ Error in commenting cycle: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if client:
            await client.disconnect()
            print("Disconnected from Telegram")


async def run_commenting_worker():
    """Main worker loop."""
    print("🚀 Telegram Commenting Worker starting...")
    print(f"   Check interval: {CHECK_INTERVAL}s")
    print(f"   DRY_RUN mode: {DRY_RUN}") 
    print(f"   OpenAI API Key: {'✓ Set' if openai.api_key else '✗ Missing'}")
    
    if not openai.api_key:
        print("❌ OPENAI_API_KEY environment variable not set!")
        return
    
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
            await commenting_cycle()
        except Exception as e:
            print(f"❌ Unexpected error in main loop: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n💤 Sleeping for {CHECK_INTERVAL}s until next cycle...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_commenting_worker())
