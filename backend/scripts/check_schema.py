import asyncio
import json
from backend.directus_client import directus

async def check():
    await directus.login()
    resp = await directus.client.get('/fields/task_queue/idempotency_key')
    print(json.dumps(resp.json(), indent=2))
    await directus.close()

if __name__ == "__main__":
    asyncio.run(check())
