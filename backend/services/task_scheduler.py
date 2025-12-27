from typing import List, Dict, Any
from datetime import datetime, timedelta

from ..directus_client import directus
from .task_queue_manager import TaskQueueManager


class TaskScheduler:
    def __init__(self):
        self.task_queue_manager = TaskQueueManager()

    async def schedule_setup_for_pending_accounts(self) -> int:
        """
        Schedule setup tasks for all accounts that need setup.
        
        Fetches all accounts from Directus where status='active' AND setup_status='pending'
        and creates a setup task for each one if one doesn't already exist.
        
        Returns:
            Number of tasks created
        """
        # Fetch accounts that need setup from Directus using consistent API
        accounts_response = await directus.get_items(
            "accounts",
            params={
                "filter[status][_eq]": "active",
                "filter[setup_status][_eq]": "pending",
                "fields": "id"
            }
        )
        
        accounts = accounts_response
        tasks_created = 0
        
        for account in accounts:
            account_id = account["id"]
            
            # Check if a setup task already exists for this account
            existing_task = await self._check_existing_setup_task(account_id)
            
            if not existing_task:
                # Create a new setup task
                task_id = await self.task_queue_manager.create_task(
                    task_type="setup_account",
                    payload={"account_id": account_id}
                )
                
                # Log the event
                await self.task_queue_manager.log_event(
                    task_id,
                    "info",
                    "scheduled",
                    f"Setup task created for account {account_id}"
                )
                
                tasks_created += 1
            else:
                # Log that we're skipping this account due to existing task
                await self.task_queue_manager.log_event(
                    existing_task["id"],
                    "info",
                    "skipped",
                    f"Setup task already exists for account {account_id}, skipping"
                )
        
        print(f"Created {tasks_created} setup tasks for pending accounts")
        return tasks_created

    async def _check_existing_setup_task(self, account_id: int) -> Dict[str, Any]:
        """
        Check if a setup task already exists for the given account.
        
        Args:
            account_id: ID of the account to check
            
        Returns:
            Task dict if exists, None otherwise
        """
        from .. import get_db_connection
        
        async with get_db_connection() as conn:
            query = """
                SELECT id, status, locked_by
                FROM task_queue
                WHERE type = 'setup_account'
                AND payload->>'account_id' = $1
                AND status IN ('pending', 'processing')
            """
            result = await conn.fetchrow(query, str(account_id))
            return dict(result) if result else None

    async def schedule_subscriptions(self) -> int:
        """
        Schedule join_channel tasks for pending subscription_queue items.
        
        Fetches pending items from subscription_queue collection (via Directus).
        For each item, creates a task in task_queue with:
        - type: 'join_channel'
        - payload: {'subscription_queue_id': item['id'], 'account_id': item['account_id'], 'channel_url': item['channel_url']}
        - run_at: Schedule them intelligently (e.g., if multiple tasks for same account, space them out by 5-10 minutes)
        
        Updates the subscription_queue item status to 'processing' (so we don't schedule it again).
        
        Returns:
            Number of tasks created
        """
        # Fetch pending subscription queue items from Directus using consistent API
        subscription_items = await directus.get_items(
            "subscription_queue",
            params={
                "filter[status][_eq]": "pending",
                "fields": "id,account_id,channel_url,found_channel_id,channel_id.id,channel_id.url"
            }
        )
        
        tasks_created = 0
        
        # Track when each account was last scheduled to space out tasks
        account_last_scheduled = {}
        
        for item in subscription_items:
            subscription_queue_id = item["id"]
            account_id = item["account_id"]
            
            # Extract channel URL based on priority: channel_url > channel_id.url > found_channel_id
            channel_url = item.get('channel_url')
            if not channel_url and item.get('channel_id'):
                channel_url = item['channel_id'].get('url')
            if not channel_url and item.get('found_channel_id'):
                # Need to fetch from found_channels collection
                channel_data = await directus.get_items(
                    "found_channels",
                    params={
                        "filter[id][_eq]": item['found_channel_id'],
                        "fields": "channel_url"
                    }
                )
                if channel_data:
                    channel_url = channel_data[0].get('channel_url')
            
            if not channel_url:
                print(f"Skipping subscription queue item {subscription_queue_id}: no channel URL found")
                # Update status to avoid reprocessing
                await directus.update_item('subscription_queue', subscription_queue_id, {
                    'status': 'failed',
                    'error_message': 'No channel URL found'
                })
                continue
            
            # Calculate run_at time to space out tasks for the same account
            run_at = datetime.utcnow()
            if account_id in account_last_scheduled:
                # Space out tasks by 5-10 minutes for same account to avoid bans
                last_run = account_last_scheduled[account_id]
                min_delay = timedelta(minutes=5)
                if run_at - last_run < min_delay:
                    run_at = last_run + min_delay
            
            # Update the subscription_queue item status to 'processing'
            await directus.update_item('subscription_queue', subscription_queue_id, {
                'status': 'processing'
            })
            
            # Create a new join_channel task
            task_id = await self.task_queue_manager.create_task(
                task_type="join_channel",
                payload={
                    "subscription_queue_id": subscription_queue_id,
                    "account_id": account_id,
                    "channel_url": channel_url
                },
                run_at=run_at
            )
            
            # Log the event
            await self.task_queue_manager.log_event(
                task_id,
                "info",
                "scheduled",
                f"Join channel task created for subscription queue item {subscription_queue_id}, account {account_id}"
            )
            
            # Update the account last scheduled time
            account_last_scheduled[account_id] = run_at
            
            tasks_created += 1
        
        print(f"Created {tasks_created} join channel tasks for subscription queue items")
        return tasks_created

    async def schedule_listener_tasks(self) -> int:
        """
        Schedule fetch_posts tasks for all active channels.
        
        Fetches active channels from Directus (status='active').
        For each channel, creates a task in task_queue with:
        - type: 'fetch_posts'
        - payload: {'channel_id': item['id'], 'channel_url': item['url'], 'last_parsed_id': item.get('last_parsed_id', 0)}
        - account_id: NOT assigned here. The worker will pick a "Listener" account dynamically.
        
        Returns:
            Number of tasks created
        """
        # Fetch active channels from Directus
        channels_response = await directus.get_items(
            "channels",
            params={
                "filter[status][_eq]": "active",
                "filter[url][_nnull]": "true",
                "fields": "id,url,last_parsed_id",
                "limit": -1
            }
        )
        
        channels = channels_response
        tasks_created = 0
        
        for channel in channels:
            channel_id = channel["id"]
            channel_url = channel["url"]
            last_parsed_id = channel.get("last_parsed_id", 0) or 0
            
            # Create a new fetch_posts task without assigning account_id
            task_id = await self.task_queue_manager.create_task(
                task_type="fetch_posts",
                payload={
                    "channel_id": channel_id,
                    "channel_url": channel_url,
                    "last_parsed_id": last_parsed_id
                }
            )
            
            # Log the event
            await self.task_queue_manager.log_event(
                task_id,
                "info",
                "scheduled",
                f"Fetch posts task created for channel {channel_id}"
            )
            
            tasks_created += 1
        
        print(f"Created {tasks_created} fetch_posts tasks for active channels")
        return tasks_created

    async def schedule_comment_tasks(self) -> int:
        """
        Schedule comment generation tasks for unhandled parsed posts.
        
        Fetches parsed_posts from Directus where status='published' for each channel individually.
        Fetches existing items from comment_queue to avoid duplicates.
        Applies basic filters based on channel template criteria.
        Creates tasks in task_queue with type='generate_comment'.
        
        Returns:
            Number of tasks created
        """
        # Fetch active channels with their templates
        channels_response = await directus.get_items(
            "channels",
            params={
                "filter[status][_eq]": "active",
                "filter[template][_nnull]": "true",
                "fields": "id,url,template.id,template.filter_mode,template.filter_keywords,template.min_post_length",
                "limit": -1
            }
        )
        
        if not channels_response:
            print("No active channels with templates found")
            return 0
        
        # Create a mapping of channel URLs to their templates
        channel_template_map = {}
        for channel in channels_response:
            channel_url = channel['url']
            template = channel.get('template', {})
            if template:
                channel_template_map[channel_url] = template
        
        if not channel_template_map:
            print("No channels with templates found")
            return 0
        
        # Get existing parsed_post_ids from comment_queue to avoid duplicates
        comment_queue_items = await directus.get_items(
            "comment_queue",
            params={
                "fields": "parsed_post_id",
                "limit": -1
            }
        )
        
        existing_post_ids = set()
        for item in comment_queue_items:
            if item.get('parsed_post_id'):
                existing_post_ids.add(item['parsed_post_id'])
        
        tasks_created = 0
        
        # Loop through each channel and fetch parsed posts specifically for that channel
        for channel_url, template in channel_template_map.items():
            # Fetch parsed posts for this specific channel
            parsed_posts = await directus.get_items(
                "parsed_posts",
                params={
                    "filter[status][_eq]": "published",
                    "filter[channel_url][_eq]": channel_url,
                    "fields": "id,channel_url,post_id,text",
                    "limit": -1
                }
            )
            
            for post in parsed_posts:
                post_id = post['id']
                post_text = post.get('text', '') or ''
                
                # Get the Telegram post_id from the parsed post
                telegram_post_id = post.get('post_id')
                
                # Skip if already in queue
                if post_id in existing_post_ids:
                    continue
                
                # Apply basic filters based on template
                if not self._post_passes_filters(post, template):
                    continue
                
                # Create a new generate_comment task
                task_id = await self.task_queue_manager.create_task(
                    task_type="generate_comment",
                    payload={
                        "parsed_post_id": post_id,
                        "telegram_post_id": telegram_post_id,
                        "post_text": post_text,
                        "channel_url": channel_url,
                        "template_id": template['id']
                    }
                )
                
                # Log the event
                await self.task_queue_manager.log_event(
                    task_id,
                    "info",
                    "scheduled",
                    f"Generate comment task created for post {post_id} on {channel_url}"
                )
                
                tasks_created += 1
        
        print(f"Created {tasks_created} generate_comment tasks for filtered posts")
        return tasks_created
    
    def _post_passes_filters(self, post: Dict[str, Any], template: Dict[str, Any]) -> bool:
        """
        Apply basic filters to determine if a post should generate a comment task.
        
        Args:
            post: The parsed post dictionary
            template: The channel template dictionary
            
        Returns:
            True if post passes all filters, False otherwise
        """
        post_text = post.get('text', '') or ''
        
        # 1. Min Length Filter
        min_length = template.get('min_post_length') or 0
        if len(post_text) < min_length:
            return False
        
        # 2. Keyword Filters
        filter_mode = template.get('filter_mode', 'none')
        filter_keywords = template.get('filter_keywords', '')
        
        if filter_mode in ['include', 'exclude'] and filter_keywords:
            keywords = [k.strip().lower() for k in filter_keywords.split(',') if k.strip()]
            text_lower = post_text.lower()
            
            matches = any(k in text_lower for k in keywords)
            
            if filter_mode == 'include' and not matches:
                return False
            if filter_mode == 'exclude' and matches:
                return False
        
        # Post passed all filters
        return True