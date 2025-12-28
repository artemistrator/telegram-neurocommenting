import asyncio
from backend.directus_client import directus  # Or wherever it's imported from

async def test_channels():
    """Test fetching channels from Directus"""
    print("=== Testing Directus Channels Collection ===\n")

    try:
        # TODO: Replace with actual collection name from your codebase
        collection_name = "channels"  # Or "tg_channels"? Find the real name!
        
        print(f"1. Attempting to fetch from collection: {collection_name}")
        
        # Attempt to fetch channels
        print("Logging into Directus...")
        await directus.login()
        print("Directus login successful")
        
        # Try to fetch channels with basic fields
        resp = await directus.client.get(
            f"/items/{collection_name}",
            params={
                "limit": 5  # Just get first 5 for testing
            }
        )
        
        print(f"Response status: {resp.status_code}")
        if resp.status_code == 200:
            result = resp.json().get("data", [])
            print(f"✅ Success! Found {len(result)} items")
            print(f"\n2. Sample data (first item):")
            
            if result and len(result) > 0:
                print(result[0])  # Show first item
            else:
                print("⚠ Collection exists but is empty")
            
            print(f"\n3. All channel URLs (if available):")
            for item in result:
                url = item.get('url', item.get('channel_url', 'N/A'))
                print(f"  - {url}")
        else:
            print(f"❌ Error: HTTP {resp.status_code}")
            print(f"Response: {resp.text}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_channels())