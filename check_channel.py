
import asyncio
from backend.directus_client import DirectusClient

async def check():
    d = DirectusClient()
    await d.login()
    print("Checking for channel with found_channel_id=13...")
    res = await d.client.get('/items/channels', params={'filter[found_channel_id][_eq]': 13})
    data = res.json().get('data', [])
    if data:
        print(f"✅ Channel found: {data[0]['username']} (ID: {data[0]['id']})")
    else:
        print("❌ Channel NOT found")

if __name__ == "__main__":
    asyncio.run(check())
