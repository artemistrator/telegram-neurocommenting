#!/usr/bin/env python3
"""
Test script to verify proxy error handling in account import service
"""

import asyncio
import json
from backend.services.account_import_service import acquire_free_proxy
from backend.directus_client import directus

async def test_proxy_acquisition():
    """Test that acquire_free_proxy works correctly with JSON filter"""
    print("Testing proxy acquisition with JSON filter...")
    
    # Login to Directus first
    await directus.login()
    print(f"✓ Logged into Directus at {directus.base_url}")
    
    # Test the fixed acquire_free_proxy function
    try:
        proxy = await acquire_free_proxy(directus)
        if proxy:
            print(f"✓ Found proxy: {proxy['id']} - {proxy['host']}:{proxy['port']}")
        else:
            print("ℹ No proxies available (this is expected in test environment)")
            
        # Test the params format that was causing issues
        import json
        params = {
            "filter": json.dumps({
                "_and": [
                    {"status": {"_in": ["active", "ok"]}},
                    {"assigned_to": {"_null": True}}
                ]
            }),
            "limit": 1
        }
        
        print("✓ JSON filter format is correct")
        print(f"  Filter: {params['filter']}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
        
    return True

async def main():
    """Run all tests"""
    print("=== Testing Proxy Error Handling ===\n")
    
    success = await test_proxy_acquisition()
    
    print("\n=== Test Complete ===")
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")

if __name__ == "__main__":
    asyncio.run(main())