"""
Comment Generation Worker

This worker processes generate_comment tasks created by the scheduler.
It generates comments using LLM and creates records in comment_queue for the executor worker.
"""

import asyncio
import os
import sys
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Set, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient
from backend.services.task_queue_manager import TaskQueueManager
import openai

# Configuration
CHECK_INTERVAL = 300  # 5 minutes
DRY_RUN = False  # Set to True to test without writing to DB (optional, but requirements say "create records")


class TaskHandler:
    async def get_supported_task_types(self) -> List[str]:
        raise NotImplementedError
    
    async def process_task(self, task: Dict[str, Any]) -> bool:
        raise NotImplementedError


# Initialize clients
directus = DirectusClient()
openai.api_key = os.getenv("OPENAI_API_KEY")

async def check_collections():
    """Verify required collections exist."""
    print("Checking Directus collections...")
    required = ["channels", "accounts", "setup_templates", "parsed_posts", "comment_queue"]
    for col in required:
        try:
            await directus.safe_get(f"/items/{col}", params={"limit": 1})
            # print(f"✓ Collection '{col}' exists")
        except Exception as e:
            print(f"⚠ WARNING: Collection '{col}' may not exist: {e}")

async def get_active_channels_with_templates() -> List[Dict]:
    """Fetch active channels that have a template assigned."""
    params = {
        "filter[status][_eq]": "active",
        "filter[template][_nnull]": "true",
        "fields": "id,url,template.*",  # Fetch template details eagerly
        "limit": -1
    }
    try:
        response = await directus.safe_get("/items/channels", params=params)
        return response.json().get('data', [])
    except Exception as e:
        print(f"Error fetching channels: {e}")
        return []

async def get_commenters_for_template(template_id: int) -> List[Dict]:
    """Fetch active commenter accounts associated with a specific template."""
    params = {
        "filter[status][_eq]": "active",
        "filter[work_mode][_eq]": "commenter",
        "filter[template_id][_eq]": template_id,
        "filter[proxy_unavailable][_neq]": "true",
        "fields": "id,phone",
        "limit": -1
    }
    try:
        response = await directus.safe_get("/items/accounts", params=params)
        return response.json().get('data', [])
    except Exception as e:
        print(f"Error fetching commenters for template {template_id}: {e}")
        return []

async def get_candidate_posts(channel_url: str) -> List[Dict]:
    """Fetch published posts for a channel."""
    params = {
        "filter[status][_eq]": "published",
        "filter[channel_url][_eq]": channel_url,
        "fields": "id,post_id,text,channel_url",
        "limit": 50, # Batch size to avoid fetching too many
        "sort": "-id"
    }
    try:
        response = await directus.safe_get("/items/parsed_posts", params=params)
        return response.json().get('data', [])
    except Exception as e:
        print(f"Error fetching posts for {channel_url}: {e}")
        return []

async def get_queued_parsed_post_ids(parsed_post_ids: List[int]) -> Set[int]:
    """Check which parsed_posts are already in the queue."""
    if not parsed_post_ids:
        return set()
    
    # We can filter by 'parsed_post_id' in list
    # Directus filter with _in
    params = {
        "filter[parsed_post_id][_in]": ",".join(map(str, parsed_post_ids)),
        "fields": "parsed_post_id",
        "limit": -1
    }
    try:
        response = await directus.safe_get("/items/comment_queue", params=params)
        data = response.json().get('data', [])
        return {item['parsed_post_id'] for item in data}
    except Exception as e:
        print(f"Error checking queue: {e}")
        return set()

async def generate_comment_with_llm(post_text: str, template: Dict) -> str:
    """Generate a comment using OpenAI based on template settings."""
    if not openai.api_key:
        return f"Test comment for post: {post_text[:20]}..."

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=openai.api_key)

        prompt_base = template.get('commenting_prompt') or "Write a relevant comment."
        style = template.get('style') or "neutral"
        tone = template.get('tone') or "casual"
        max_words = template.get('max_words', 30)

        system_prompt = (
            f"You are a social media user. {prompt_base}\n"
            f"Style: {style}\n"
            f"Tone: {tone}\n"
            f"Keep it under {max_words} words."
        )

        user_prompt = f"Post content:\n{post_text}\n\nWrite a comment:"

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=60
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"LLM Generation Error: {e}")
        return f"Nice post! (fallback due to error)"

def check_filters(post: Dict, template: Dict) -> bool:
    """
    Apply filters to determine if post should be commented.
    Returns True if passed, False otherwise.
    """
    text = post.get('text', '') or ''
    
    # 1. Min Length
    min_length = template.get('min_post_length') or 0
    if len(text) < min_length:
        return False

    # 2. Keywords
    filter_mode = template.get('filter_mode', 'none') # none, include, exclude
    keywords_str = template.get('filter_keywords', '')
    if filter_mode in ['include', 'exclude'] and keywords_str:
        keywords = [k.strip().lower() for k in keywords_str.split(',') if k.strip()]
        text_lower = text.lower()
        
        matches = any(k in text_lower for k in keywords)
        
        if filter_mode == 'include' and not matches:
            return False
        if filter_mode == 'exclude' and matches:
            return False

    # 3. Skip reposts (Stub)
    # if template.get('skip_reports'): ...

    return True


class CommentGenerationTaskHandler(TaskHandler):
    async def get_supported_task_types(self) -> List[str]:
        return ['generate_comment']

    async def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a generate_comment task.
        
        Args:
            task: Task dictionary with type 'generate_comment' and payload
            
        Returns:
            True if task was processed successfully, False otherwise
        """
        print(f"\n📝 Processing generate_comment task: {task['id']}")
        
        task_payload = task['payload']
        parsed_post_id = task_payload['parsed_post_id']
        telegram_post_id = task_payload.get('telegram_post_id')  # Get the Telegram post_id
        post_text = task_payload['post_text']
        channel_url = task_payload['channel_url']
        template_id = task_payload['template_id']
        
        # Step 1: Fetch template details from Directus
        try:
            template = await directus.get_item("setup_templates", template_id)
            if not template:
                error_msg = f"Template with ID {template_id} not found"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error fetching template {template_id}: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # Step 2: Generate Comment using existing generate_comment_with_llm logic
        comment_text = await generate_comment_with_llm(post_text, template)
        
        if not comment_text:
            error_msg = f"Failed to generate comment for post {parsed_post_id}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # Step 3: Select Account using existing get_commenters_for_template logic
        commenters = await get_commenters_for_template(template_id)
        
        if not commenters:
            error_msg = f"No available commenters for template {template_id}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # Pick a random commenter account
        selected_account = random.choice(commenters)
        
        print(f"Using commenter account: {selected_account['phone']}")
        
        # Step 4: Queue for Posting - Create record in comment_queue
        try:
            queue_data = {
                "status": "pending",
                "account_id": selected_account['id'],
                "parsed_post_id": parsed_post_id,
                "channel_url": channel_url,
                "post_id": telegram_post_id,  # Using the correct Telegram post_id
                "generated_comment": comment_text,
                "error_message": None
            }
            
            await directus.create_item("comment_queue", queue_data)
            
            print(f"✓ Comment queued for posting: post {parsed_post_id}, account {selected_account['id']}")
            return True
            
        except Exception as e:
            error_msg = f"Error creating comment queue entry: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)


async def run_comment_generation_worker():
    print("🚀 Comment Generation Worker starting with TaskQueueManager...")
    if not openai.api_key:
        print("⚠ OPENAI_API_KEY not set. Comments will be stubs.")
    
    try:
        await directus.login()
        print("✓ Logged in to Directus")
    except Exception as e:
        print(f"❌ Directus Login Failed: {e}")
        return
    
    await check_collections()
    
    # Initialize TaskQueueManager with CommentGenerationTaskHandler
    task_queue_manager = TaskQueueManager()
    comment_handler = CommentGenerationTaskHandler()
    
    print("Starting TaskQueueManager with CommentGenerationTaskHandler...")
    
    # Run the TaskQueueManager (this handles the main loop)
    worker_id = 'comment-generation-worker'
    task_types = await comment_handler.get_supported_task_types()
    
    print(f"Listening for tasks: {task_types}, worker_id: {worker_id}")
    
    while True:
        try:
            # Claim a task from the queue
            task = await task_queue_manager.claim_task(worker_id, task_types)
            
            if task:
                print(f"Claimed task {task['id']} of type {task['type']}")
                try:
                    success = await comment_handler.process_task(task)
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
    asyncio.run(run_comment_generation_worker())
