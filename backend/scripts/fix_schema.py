import asyncio
import json
from backend.directus_client import directus

async def fix_schema():
    await directus.login()
    print(">>> Attempting to set unique constraint on idempotency_key...")
    
    # First, let's see current schema again to be sure
    resp = await directus.client.get("/fields/task_queue/idempotency_key")
    current = resp.json().get('data', {})
    
    # Update schema to unique
    # In Directus, we patch the field.
    payload = {
        "schema": {
            "is_unique": True
        }
    }
    resp = await directus.client.patch("/fields/task_queue/idempotency_key", json=payload)
    if resp.status_code in [200, 204]:
        print("SUCCESS: Unique constraint applied.")
    else:
        print(f"FAILED: {resp.status_code} {resp.text}")
    
    await directus.close()

if __name__ == "__main__":
    asyncio.run(fix_schema())
