import asyncio
import os
from backend.directus_client import directus

async def test_comments():
    """Test fetching comments from Directus comment_queue collection"""
    print("=== Testing Directus Comment Queue Collection ===\n")
    
    try:
        # Login first
        print("1. Logging into Directus...")
        await directus.login()
        print("Directus login successful")
        
        # Try to get all comments from comment_queue collection
        print("\n2. Fetching all comments from 'comment_queue' collection...")
        comments = await directus.get_items("comment_queue")
        
        print(f"✅ Success! Found {len(comments)} comments in collection")
        
        if comments:
            print(f"\n3. Sample comment data (first item):")
            print(comments[0])
            
            print(f"\n4. All comments with status and channel_url:")
            for comment in comments:
                print(f"  - ID: {comment.get('id')}, Channel: {comment.get('channel_url')}, Status: {comment.get('status')}, Posted: {comment.get('posted_at')}")
        else:
            print("ℹ️  Comment queue collection is empty")
        
        # Try to get comments with different status filters
        print("\n5. Fetching comments with status 'posted'...")
        posted_comments = await directus.get_items("comment_queue", params={
            "filter": {"status": {"_eq": "posted"}}
        })
        print(f"Posted comments: {len(posted_comments)}")
        
        print("\n6. Fetching comments with status 'pending'...")
        pending_comments = await directus.get_items("comment_queue", params={
            "filter": {"status": {"_eq": "pending"}}
        })
        print(f"Pending comments: {len(pending_comments)}")
        
        print("\n7. Fetching comments with status 'failed'...")
        failed_comments = await directus.get_items("comment_queue", params={
            "filter": {"status": {"_eq": "failed"}}
        })
        print(f"Failed comments: {len(failed_comments)}")
        
        print("\n8. Fetching all comments regardless of status...")
        all_comments = await directus.get_items("comment_queue", params={
            "fields": "id,channel_url,posted_at,status,created_at"
        })
        print(f"All comments: {len(all_comments)}")
        
        for comment in all_comments:
            print(f"  - ID: {comment.get('id')}, Channel: {comment.get('channel_url')}, Status: {comment.get('status')}, Posted: {comment.get('posted_at')}, Created: {comment.get('created_at')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_comments())