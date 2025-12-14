import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class DirectusClient:
    def __init__(self):
        self.base_url = os.getenv("DIRECTUS_PUBLIC_URL", "http://localhost:8055")
        self.email = os.getenv("DIRECTUS_ADMIN_EMAIL")
        self.password = os.getenv("DIRECTUS_ADMIN_PASSWORD")
        self.token = None
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def login(self):
        try:
            # Читаем токен из .env
            static_token = os.getenv("DIRECTUS_TOKEN")
            
            if not static_token:
                raise Exception("DIRECTUS_TOKEN not found in .env file")
        
            self.token = static_token
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
            print("✅ Directus Login Successful")
        
        except Exception as e:
            print(f"❌ Directus Login Failed: {e}")
            raise


    async def get_accounts(self, status="active"):
        if not self.token:
            await self.login()
        
        response = await self.client.get("/items/accounts", params={
            "filter[status][_eq]": status,
            "fields": "*.*" # Забрать все поля
        })
        return response.json()['data']
        
    async def create_account(self, data):
        if not self.token:
            await self.login()
            
        response = await self.client.post("/items/accounts", json=data)
        return response.json()['data']

    # Закрыть соединение при остановке скрипта
    async def close(self):
        await self.client.aclose()

        # ... (предыдущие методы) ...

    async def update_item(self, collection, item_id, data):
        """Обновление записи (например, смена статуса)"""
        if not self.token:
            await self.login()
        
        response = await self.client.patch(f"/items/{collection}/{item_id}", json=data)
        response.raise_for_status()
        return response.json()['data']

    async def create_item(self, collection, data):
        """Создание записи в любой коллекции"""
        if not self.token:
            await self.login()
        
        response = await self.client.post(f"/items/{collection}", json=data)
        response.raise_for_status()
        return response.json()['data']

    async def download_file(self, file_id, save_path):
        """Скачивание файла из Directus на диск"""
        if not self.token:
            await self.login()
            
        # В Directus файлы лежат по адресу /assets/{id}
        async with self.client.stream('GET', f"/assets/{file_id}") as response:
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
        print(f"📥 File downloaded to {save_path}")

    async def get_available_proxy(self, user_id):
        """
        Найти свободный прокси для пользователя
        Критерии: status='ok', assigned_to=null, user_created=user_id
        """
        if not self.token:
            await self.login()
        
        try:
            response = await self.client.get("/items/proxies", params={
                "filter[status][_eq]": "active",
                "filter[assigned_to][_null]": "true",
                "limit": 1,
                "fields": "id,host,port,type"
            })
            response.raise_for_status()
            data = response.json()
            proxies = data.get('data', [])
            
            if proxies:
                return proxies[0]
            return None
            
        except Exception as e:
            print(f"⚠️ Error finding available proxy: {e}")
            return None

    async def get_item(self, collection, item_id):
        """Get a single item from a collection by ID"""
        if not self.token:
            await self.login()
        
        try:
            response = await self.client.get(f"/items/{collection}/{item_id}")
            response.raise_for_status()
            data = response.json()
            return data.get('data')
        except Exception as e:
            print(f"Error getting item {item_id} from {collection}: {e}")
            return None


# Глобальный экземпляр
directus = DirectusClient()
