#!/usr/bin/env python3
"""
Debug script to diagnose dashboard data issues
This script connects to Directus and checks the actual data in the collections
"""
import sys
import os
import asyncio

# Set the Directus URL to localhost before importing
os.environ["DIRECTUS_URL"] = "http://localhost:18055"

# Add the backend directory to the path so we can import directus_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.directus_client import directus

async def debug_dashboard_data():
    print("Starting dashboard data diagnosis...")
    
    try:
        # Get Directus client instance
        client = directus
        print("Successfully connected to Directus")
        
        # Check accounts collection
        print("\n--- Accounts Collection ---")
        try:
            accounts_response = await client.safe_get("/items/accounts", params={
                "fields": "*.*",
                "limit": -1
            })
            accounts_response.raise_for_status()
            all_accounts = accounts_response.json().get('data', [])
            total_accounts = len(all_accounts)
            
            active_accounts = [acc for acc in all_accounts if acc.get('status') == 'active']
            banned_accounts = [acc for acc in all_accounts if acc.get('status') == 'banned']
            
            print(f"Total accounts: {total_accounts}")
            print(f"Active accounts: {len(active_accounts)}")
            print(f"Banned accounts: {len(banned_accounts)}")
            
            if all_accounts:
                print("Sample account data:")
                for i, acc in enumerate(all_accounts[:3]):  # Show first 3 accounts
                    print(f"  Account {i+1}: id={acc.get('id')}, phone={acc.get('phone')}, status={acc.get('status')}, user_created={acc.get('user_created')}")
        except Exception as e:
            print(f"Error fetching accounts: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check proxies collection
        print("\n--- Proxies Collection ---")
        try:
            proxies_response = await client.safe_get("/items/proxies", params={
                "fields": "*.*",
                "limit": -1
            })
            proxies_response.raise_for_status()
            all_proxies = proxies_response.json().get('data', [])
            total_proxies = len(all_proxies)
            
            active_proxies = [proxy for proxy in all_proxies if proxy.get('status') == 'active']
            
            print(f"Total proxies: {total_proxies}")
            print(f"Active proxies: {len(active_proxies)}")
            
            if all_proxies:
                print("Sample proxy data:")
                for i, proxy in enumerate(all_proxies[:3]):  # Show first 3 proxies
                    print(f"  Proxy {i+1}: id={proxy.get('id')}, ip={proxy.get('ip')}, status={proxy.get('status')}, user_created={proxy.get('user_created')}")
        except Exception as e:
            print(f"Error fetching proxies: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check comment_queue collection
        print("\n--- Comment Queue Collection ---")
        try:
            comment_queue_response = await client.safe_get("/items/comment_queue", params={
                "sort": "-created_at",
                "limit": 5,
                "fields": "*.*"
            })
            comment_queue_response.raise_for_status()
            comment_queue_items = comment_queue_response.json().get('data', [])
            
            print(f"Total comment queue items: {len(comment_queue_items)}")
            
            if comment_queue_items:
                print("Latest 5 comment queue items:")
                for i, item in enumerate(comment_queue_items):
                    print(f"  Item {i+1}: id={item.get('id')}, status={item.get('status')}, posted_at={item.get('posted_at')}, account_id={item.get('account_id')}, user_created={item.get('user_created')}")
            else:
                print("No comment queue items found")
        except Exception as e:
            print(f"Error fetching comment_queue: {str(e)}")
            import traceback
            traceback.print_exc()
            
        # Check for any recent comments that might be in other collections
        print("\n--- Comments Collection (if exists) ---")
        try:
            comments_response = await client.safe_get("/items/comments", params={
                "sort": "-created_at",
                "limit": 5,
                "fields": "*.*"
            })
            comments_response.raise_for_status()
            comments_items = comments_response.json().get('data', [])
            
            print(f"Total comments: {len(comments_items)}")
            
            if comments_items:
                print("Latest 5 comments:")
                for i, item in enumerate(comments_items):
                    print(f"  Comment {i+1}: id={item.get('id')}, text={item.get('text')[:50]}..., created_at={item.get('created_at')}")
            else:
                print("No comments found in 'comments' collection")
        except Exception as e:
            print(f"Collection 'comments' might not exist: {str(e)}")
        
    except Exception as e:
        print(f"Error connecting to Directus: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_dashboard_data())