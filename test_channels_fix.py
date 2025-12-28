import asyncio
import os
from backend.directus_client import directus

async def test_channels():
    """Test fetching channels from Directus after the URL fix"""
    print("=== Testing Directus Channels Collection After URL Fix ===\n")
    
    try:
        # Attempt to fetch channels
        print("1. Attempting to fetch channels from Directus...")
        
        # Login first
        print("Logging into Directus...")
        await directus.login()
        print("Directus login successful")
        
        # Try to get all items from channels collection
        print("\n2. Fetching all items from 'channels' collection...")
        channels = await directus.get_items("channels")
        
        print(f"✅ Success! Found {len(channels)} channels in collection")
        
        if channels:
            print(f"\n3. Sample channel data (first item):")
            print(channels[0])
        else:
            print("ℹ️  Channels collection is empty - this is expected if no channels have been added yet")
        
        # Try to get collections list to see all available collections
        print("\n4. Fetching list of all collections...")
        collections_response = await directus.client.get("/collections")
        collections_data = collections_response.json()
        collections = collections_data.get('data', [])
        
        print(f"Available collections ({len(collections)}):")
        for collection in collections:
            print(f"  - {collection.get('collection')}")
        
        # Check if there's a collection that might contain channels with a different name
        channel_collections = [c for c in collections if 'channel' in c.get('collection', '').lower()]
        if channel_collections:
            print(f"\n5. Potential channel collections found:")
            for col in channel_collections:
                print(f"  - {col.get('collection')}")
                
                # Try to get items from each potential channel collection
                try:
                    items = await directus.get_items(col.get('collection'))
                    print(f"    Items: {len(items)}")
                except Exception as e:
                    print(f"    Error accessing: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_channels())