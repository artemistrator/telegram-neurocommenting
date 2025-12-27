#!/usr/bin/env python3
"""
Schema inspection script to get exact field names from Directus collections
This will help us identify the correct field names to use in the dashboard
"""
import sys
import os
import asyncio

# Set the Directus URL to localhost before importing
os.environ["DIRECTUS_URL"] = "http://localhost:18055"

# Add the backend directory to the path so we can import directus_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.directus_client import directus

async def inspect_schema():
    print("Starting Directus schema inspection...")
    
    try:
        # Get Directus client instance
        client = directus
        print("Successfully connected to Directus")
        
        # Check accounts collection
        print("\n--- Accounts Collection ---")
        try:
            accounts_response = await client.safe_get("/items/accounts", params={
                "limit": 1  # Just get one record to inspect fields
            })
            accounts_response.raise_for_status()
            accounts_data = accounts_response.json().get('data', [])
            
            if accounts_data:
                account_fields = list(accounts_data[0].keys())
                print(f"Accounts Fields: {account_fields}")
                print(f"Sample account record: {accounts_data[0]}")
            else:
                print("No accounts found")
        except Exception as e:
            print(f"Error fetching accounts: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check proxies collection
        print("\n--- Proxies Collection ---")
        try:
            proxies_response = await client.safe_get("/items/proxies", params={
                "limit": 1  # Just get one record to inspect fields
            })
            proxies_response.raise_for_status()
            proxies_data = proxies_response.json().get('data', [])
            
            if proxies_data:
                proxy_fields = list(proxies_data[0].keys())
                print(f"Proxies Fields: {proxy_fields}")
                print(f"Sample proxy record: {proxies_data[0]}")
            else:
                print("No proxies found")
        except Exception as e:
            print(f"Error fetching proxies: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check comment_queue collection
        print("\n--- Comment Queue Collection ---")
        try:
            comment_queue_response = await client.safe_get("/items/comment_queue", params={
                "limit": 1  # Just get one record to inspect fields
            })
            comment_queue_response.raise_for_status()
            comment_queue_data = comment_queue_response.json().get('data', [])
            
            if comment_queue_data:
                comment_queue_fields = list(comment_queue_data[0].keys())
                print(f"Comment Queue Fields: {comment_queue_fields}")
                print(f"Sample comment queue record: {comment_queue_data[0]}")
            else:
                print("No comment queue items found")
        except Exception as e:
            print(f"Error fetching comment_queue: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check task_queue collection
        print("\n--- Task Queue Collection ---")
        try:
            task_queue_response = await client.safe_get("/items/task_queue", params={
                "limit": 1  # Just get one record to inspect fields
            })
            task_queue_response.raise_for_status()
            task_queue_data = task_queue_response.json().get('data', [])
            
            if task_queue_data:
                task_queue_fields = list(task_queue_data[0].keys())
                print(f"Task Queue Fields: {task_queue_fields}")
                print(f"Sample task queue record: {task_queue_data[0]}")
            else:
                print("No task queue items found")
        except Exception as e:
            print(f"Error fetching task_queue: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check subscription_queue collection
        print("\n--- Subscription Queue Collection ---")
        try:
            subscription_queue_response = await client.safe_get("/items/subscription_queue", params={
                "limit": 1  # Just get one record to inspect fields
            })
            subscription_queue_response.raise_for_status()
            subscription_queue_data = subscription_queue_response.json().get('data', [])
            
            if subscription_queue_data:
                subscription_queue_fields = list(subscription_queue_data[0].keys())
                print(f"Subscription Queue Fields: {subscription_queue_fields}")
                print(f"Sample subscription queue record: {subscription_queue_data[0]}")
            else:
                print("No subscription queue items found")
        except Exception as e:
            print(f"Error fetching subscription_queue: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check task_events collection
        print("\n--- Task Events Collection ---")
        try:
            task_events_response = await client.safe_get("/items/task_events", params={
                "limit": 1  # Just get one record to inspect fields
            })
            task_events_response.raise_for_status()
            task_events_data = task_events_response.json().get('data', [])
            
            if task_events_data:
                task_events_fields = list(task_events_data[0].keys())
                print(f"Task Events Fields: {task_events_fields}")
                print(f"Sample task events record: {task_events_data[0]}")
            else:
                print("No task events found")
        except Exception as e:
            print(f"Error fetching task_events: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check found_posts collection
        print("\n--- Found Posts Collection ---")
        try:
            found_posts_response = await client.safe_get("/items/found_posts", params={
                "limit": 1  # Just get one record to inspect fields
            })
            found_posts_response.raise_for_status()
            found_posts_data = found_posts_response.json().get('data', [])
            
            if found_posts_data:
                found_posts_fields = list(found_posts_data[0].keys())
                print(f"Found Posts Fields: {found_posts_fields}")
                print(f"Sample found posts record: {found_posts_data[0]}")
            else:
                print("No found posts found")
        except Exception as e:
            print(f"Error fetching found_posts: {str(e)}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"Error connecting to Directus: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(inspect_schema())