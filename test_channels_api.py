import asyncio
import os
import logging
from backend.routers.channels import _get_channels_from_directus

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)

async def test_channels_api():
    """Test the same function that the API uses to fetch channels"""
    print("=== Testing Channels API Function ===\n")
    
    try:
        # Call the same function that the API endpoint uses
        result = await _get_channels_from_directus()
        
        print(f"✅ Success! API function returned data:")
        print(f"  Success: {result.get('success')}")
        print(f"  Channels count: {len(result.get('channels', []))}")
        print(f"  Stats: {result.get('stats')}")
        
        if result.get('channels'):
            print(f"\nFirst channel data:")
            print(result['channels'][0])
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_channels_api())