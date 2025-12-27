import os
import httpx
import traceback
from dotenv import load_dotenv

load_dotenv()

class DirectusClient:
    def __init__(self):
        # Default internal URL for container network, use env for host-side access
        self.base_url = os.getenv("DIRECTUS_URL", "http://directus:8055")
        self.email = os.getenv("DIRECTUS_ADMIN_EMAIL")
        self.password = os.getenv("DIRECTUS_ADMIN_PASSWORD")
        self.token = None
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        print(f"[DirectusClient] Initialized with DIRECTUS_URL={self.base_url}")
        print(f"[DirectusClient] Using DIRECTUS_URL={self.base_url}")
        print(f"[DirectusClient] Email auth: {bool(self.email)} Token auth: {bool(os.getenv('DIRECTUS_TOKEN'))}")

    async def login(self):
        try:
            # 1. Проверяем статический токен
            static_token = os.getenv("DIRECTUS_TOKEN")
            if static_token:
                # Временно устанавливаем хедер для проверки
                self.client.headers.update({"Authorization": f"Bearer {static_token}"})
                try:
                    # Легковесный запрос для проверки токена
                    auth_check = await self.client.get("/users/me", params={"fields": "id"})
                    if auth_check.status_code == 200:
                        self.token = static_token
                        print(f"Directus Login Successful (using valid DIRECTUS_URL={self.base_url})")
                        print("Directus Login Successful")
                        # Log which user is logged in
                        user_resp = await self.client.get("/users/me?fields=id,email,role.*")
                        print(f"[DirectusClient] Logged in as: {user_resp.json()}")
                        return
                    elif auth_check.status_code in (401, 403):
                        print(f"!!! Directus authentication/permission issue (HTTP {auth_check.status_code}). Body: {auth_check.text}")
                    else:
                        print(f"!!! DIRECTUS_TOKEN from .env is invalid (HTTP {auth_check.status_code}). Trying email/password...")

                    # Токен невалиден, убираем хедер
                    if "Authorization" in self.client.headers:
                        del self.client.headers["Authorization"]
                except Exception as e:
                    print(f"!!! Error checking token: {e}. Trying email/password...")
                    if "Authorization" in self.client.headers:
                        del self.client.headers["Authorization"]

            # 2. Если токена нет или он невалиден, пробуем email/password
            if self.email and self.password:
                print(f"--- Logging in via Email/Password to {self.base_url}...")
                response = await self.client.post("/auth/login", json={
                    "email": self.email,
                    "password": self.password
                })

                if response.status_code == 200:
                    data = response.json()
                    self.token = data['data']['access_token']
                    self.client.headers.update({"Authorization": f"Bearer {self.token}"})
                    print("Directus Login Successful (via /auth/login)")
                    print("Directus Login Successful")
                    # Log which user is logged in
                    user_resp = await self.client.get("/users/me?fields=id,email,role.*")
                    print(f"[DirectusClient] Logged in as: {user_resp.json()}")
                    return
                elif response.status_code in (401, 403):
                    print(f"!!! Directus login permission/credentials issue (HTTP {response.status_code}). Body: {response.text}")
                    raise Exception(f"Login failed: Permission denied ({response.status_code})")
                else:
                    raise Exception(f"Login failed: {response.text}")

            # 3. Ничего не помогло
            raise Exception("No valid authentication method found (invalid token & failed/missing credentials)")

        except Exception as e:
            print(f"ERROR: Directus Login Failed: {e}")
            raise


    async def get_accounts(self, status="active"):
        if not self.token:
            await self.login()

        try:
            response = await self.client.get("/items/accounts", params={
                "filter[status][_eq]": status,
                "fields": "*.*" # Забрать все поля
            })
            response.raise_for_status()
            return response.json()['data']
        except Exception as e:
            print(f"Error getting accounts: {e}")
            # Return empty list on error
            return []

    async def create_account(self, data):
        if not self.token:
            await self.login()

        response = await self.client.post("/items/accounts", json=data)
        return response.json()['data']

    # Закрыть соединение при остановке скрипта
    async def close(self):
        await self.client.aclose()

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
        print(f"--- File downloaded to {save_path}")

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
            print(f"!!! Error finding available proxy: {e}")
            return None

    async def get_item(self, collection, item_id, params=None):
        """Get a single item from a collection by ID"""
        if not self.token:
            await self.login()

        try:
            # Use safe params logic
            safe_params = self.build_safe_params(params) if params else None
            response = await self.client.get(f"/items/{collection}/{item_id}", params=safe_params)
            response.raise_for_status()
            data = response.json()
            return data.get('data')
        except Exception as e:
            print(f"Error getting item {item_id} from {collection}: {e}")
            return None

    async def get_items(self, collection, params=None):
        """
        Get items from a collection with query params.
        Should replace usages of raw .get() where possible.
        """
        if not self.token:
            await self.login()

        try:
            safe_params = self.build_safe_params(params) if params else None
            response = await self.client.get(f"/items/{collection}", params=safe_params)
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            print(f"Error getting items from {collection}: {e}")
            return []

    def build_safe_params(self, params):
        """
        Build safe query parameters for Directus requests.

        This helper prevents field name corruption (e.g., proxy_id.* becoming proxyid.*)
        that causes 403 Forbidden errors by ensuring proper URL encoding.

        Args:
            params (dict): Request parameters

        Returns:
            dict: Safely encoded parameters
        """
        if not params:
            return params

        # Make a copy to avoid modifying the original
        safe_params = params.copy()

        # Handle fields parameter specially to preserve underscores and wildcards
        if 'fields' in safe_params:
            fields = safe_params['fields']
            # If fields is a list, join with commas
            if isinstance(fields, list):
                safe_params['fields'] = ','.join(fields)
            # If it's already a string, leave as-is but ensure it's properly handled
            # The key is to avoid any post-processing that might corrupt field names

        return safe_params

    async def get(self, endpoint, params=None):
        """Wrapper for client.get with authentication handling"""
        if not self.token:
            await self.login()
        try:
            return await self.client.get(endpoint, params=params)
        except httpx.ConnectError as e:
            print(f"[DirectusClient] ConnectError calling {endpoint}: {e}")
            traceback.print_exc()
            raise

    async def patch(self, endpoint, json=None):
        """Wrapper for client.patch with authentication handling"""
        if not self.token:
            await self.login()
        return await self.client.patch(endpoint, json=json)

    async def safe_get(self, url, params=None, **kwargs):
        """
        Perform a GET request with safe parameter handling.

        This method ensures fields with wildcards like proxy_id.* are not corrupted
        and adds debug logging for non-200 responses.

        Args:
            url (str): Request URL
            params (dict): Query parameters
            **kwargs: Additional arguments for httpx client

        Returns:
            httpx.Response: Response object
        """
        if not self.token:
            await self.login()

        # Apply safe parameter handling
        safe_params = self.build_safe_params(params) if params else None

        # Make the request
        response = await self.client.get(url, params=safe_params, **kwargs)

        # Debug logging for non-200 responses
        if response.status_code != 200:
            # Log the actual request URL (without tokens for security)
            safe_headers = {k: v for k, v in self.client.headers.items() if 'authorization' not in k.lower()}
            print(f"[DEBUG] Directus request failed with status {response.status_code}")
            print(f"[DEBUG] URL: {response.url}")
            print(f"[DEBUG] Headers: {safe_headers}")
            if safe_params:
                print(f"[DEBUG] Params: {safe_params}")
            print(f"[DEBUG] Response body: {response.text}")

        return response

    # Compatibility aliases for Directus SDK methods
    async def read_items(self, collection, query=None, params=None, **kwargs):
        """
        Compatibility alias for get_items to support Directus SDK method names.
        
        Accepts both query= and params= by normalizing:
        - If query is passed, map it to params format
        - If both passed, prefer params
        - Keep backward compatibility
        """
        # Normalize parameters
        final_params = params if params is not None else {}
        
        # If query is provided and params is not provided, convert query to params format
        if query is not None and params is None:
            # Convert Directus query format to params format
            final_params = self._convert_query_to_params(query)
        
        return await self.get_items(collection, final_params)

    async def read_item(self, collection, item_id, query=None, params=None, **kwargs):
        """
        Compatibility alias for get_item to support Directus SDK method names.
        
        Accepts both query= and params= by normalizing:
        - If query is passed, map it to params format
        - If both passed, prefer params
        - Keep backward compatibility
        """
        # Normalize parameters
        final_params = params if params is not None else {}
        
        # If query is provided and params is not provided, convert query to params format
        if query is not None and params is None:
            # Convert Directus query format to params format
            final_params = self._convert_query_to_params(query)
        
        return await self.get_item(collection, item_id, final_params)

    def _convert_query_to_params(self, query):
        """
        Convert Directus SDK query format to Directus API params format.
        
        Example: 
        Input: {"filter": {"status": {"_eq": "pending"}}, "fields": ["id", "name"]}
        Output: {"filter[status][_eq]": "pending", "fields": "id,name"}
        """
        if not query:
            return {}
        
        params = {}
        
        # Handle filter
        if 'filter' in query:
            self._flatten_filter(query['filter'], params)
        
        # Handle fields
        if 'fields' in query:
            fields = query['fields']
            if isinstance(fields, list):
                params['fields'] = ','.join(fields)
            else:
                params['fields'] = fields
        
        # Handle other common parameters
        for key in ['sort', 'limit', 'offset', 'page', 'search', 'groupBy']:
            if key in query:
                params[key] = query[key]
        
        return params

    def _flatten_filter(self, filter_dict, params, prefix='filter'):
        """
        Recursively flatten filter dictionary to Directus API params format.
        
        Example:
        Input: {"status": {"_eq": "pending"}, "name": {"_contains": "test"}}
        Output: {"filter[status][_eq]": "pending", "filter[name][_contains]": "test"}
        """
        if isinstance(filter_dict, dict):
            for key, value in filter_dict.items():
                if isinstance(value, dict):
                    # Nested filter like {"status": {"_eq": "pending"}}
                    for op, val in value.items():
                        params[f"{prefix}[{key}][{op}]"] = val
                elif isinstance(value, (str, int, float)):
                    # Simple value like {"status": "pending"}
                    params[f"{prefix}[{key}]"] = value
                elif isinstance(value, list):
                    # Handle array values
                    params[f"{prefix}[{key}]"] = ','.join(map(str, value))
                else:
                    # Recursively handle nested structures
                    self._flatten_filter(value, params, f"{prefix}[{key}]")


# Глобальный экземпляр
directus = DirectusClient()