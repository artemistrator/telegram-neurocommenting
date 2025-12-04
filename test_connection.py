import asyncio
from backend.directus_client import directus

async def main():
    print("Connecting to Directus...")
    await directus.login()
    
    # Пробуем создать тестовый аккаунт
    try:
        new_acc = await directus.create_account({
            "phone": "+79990001122",
            "status": "active",
            "work_mode": "listener"
        })
        print(f"Created account: {new_acc['id']}")
        
        # Пробуем прочитать
        accounts = await directus.get_accounts()
        print(f"Total accounts found: {len(accounts)}")
        print(accounts)
        
    except Exception as e:
        print(f"Error: {e}")
    
    await directus.close()

if __name__ == "__main__":
    asyncio.run(main())
