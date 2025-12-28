import asyncio
import os
from backend.directus_client import directus

async def test_channels_simple():
    """Test fetching channels with simple query vs complex query"""
    print("=== Testing Directus Channels Access ===\n")
    
    try:
        # Login first
        print("1. Logging into Directus...")
        await directus.login()
        print("Directus login successful")
        
        # Try simple query first
        print("\n2. Testing simple query (no field expansion)...")
        try:
            response = await directus.client.get("/items/channels", params={
                "fields": "id,url,title,status"
            })
            print(f"Simple query status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Simple query success: {len(data.get('data', []))} items")
                if data.get('data'):
                    print(f"Sample: {data['data'][0]}")
            else:
                print(f"Simple query failed: {response.text}")
        except Exception as e:
            print(f"Simple query error: {e}")
        
        # Try the complex query that the API uses
        print("\n3. Testing complex query (with template expansion)...")
        try:
            response = await directus.client.get("/items/channels", params={
                "fields": "id,url,title,subscribers_count,status,source,last_parsed_id,found_channel_id,template.id,template.name,date_created,last_comment_date,comments_count",
                "sort": "-id",
                "limit": -1
            })
            print(f"Complex query status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Complex query success: {len(data.get('data', []))} items")
                if data.get('data'):
                    print(f"Sample: {data['data'][0]}")
            else:
                print(f"Complex query failed: {response.text}")
        except Exception as e:
            print(f"Complex query error: {e}")
            
        # Try without template expansion
        print("\n4. Testing query without template expansion...")
        try:
            response = await directus.client.get("/items/channels", params={
                "fields": "id,url,title,subscribers_count,status,source,last_parsed_id,found_channel_id,date_created,last_comment_date,comments_count",
                "sort": "-id",
                "limit": -1
            })
            print(f"No-template query status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"No-template query success: {len(data.get('data', []))} items")
                if data.get('data'):
                    print(f"Sample: {data['data'][0]}")
            else:
                print(f"No-template query failed: {response.text}")
        except Exception as e:
            print(f"No-template query error: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_channels_simple())