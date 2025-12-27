import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import os
import io
import zipfile
import json
from pathlib import Path

# Добавляем корневую папку в sys.path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.account_import_service import import_accounts_from_zip

class TestAccountImportService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Mock directus_client
        self.directus_patcher = patch("backend.services.account_import_service.directus")
        self.mock_directus = self.directus_patcher.start()
        
        # httpx mock response setup
        self.mock_response = MagicMock()
        self.mock_response.json.return_value = {"data": []}
        self.mock_response.raise_for_status = MagicMock()
        
        self.mock_directus.client.get = AsyncMock(return_value=self.mock_response)
        self.mock_directus.client.post = AsyncMock(return_value=self.mock_response)
        self.mock_directus.create_item = AsyncMock()
        self.mock_directus.update_item = AsyncMock()
        self.mock_directus.get_available_proxy = AsyncMock(return_value=None)

        # Mock Telethon
        self.telethon_patcher = patch("backend.services.account_import_service.TelegramClient")
        self.mock_telegram_client_class = self.telethon_patcher.start()
        self.mock_client = MagicMock()
        self.mock_client.connect = AsyncMock()
        self.mock_client.is_user_authorized = AsyncMock(return_value=True)
        self.mock_client.disconnect = AsyncMock()
        self.mock_client.session = MagicMock()
        self.mock_telegram_client_class.return_value = self.mock_client

        # Mock StringSession
        self.string_session_patcher = patch("backend.services.account_import_service.StringSession")
        self.mock_string_session = self.string_session_patcher.start()
        self.mock_string_session.save.return_value = "MOCK_SESSION_STRING"

        # Mock acquire_free_proxy
        self.acquire_proxy_patcher = patch("backend.services.account_import_service.acquire_free_proxy")
        self.mock_acquire_proxy = self.acquire_proxy_patcher.start()
        self.mock_acquire_proxy.return_value = None # Default no proxy

        # Mock Environment variables
        self.env_patcher = patch.dict(os.environ, {
            "TELEGRAM_API_ID": "2222",
            "TELEGRAM_API_HASH": "env_hash"
        })
        self.env_patcher.start()

    def tearDown(self):
        self.directus_patcher.stop()
        self.telethon_patcher.stop()
        self.string_session_patcher.stop()
        self.env_patcher.stop()
        self.acquire_proxy_patcher.stop()

    def create_mock_zip(self, files_dict):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name, content in files_dict.items():
                zf.writestr(name, content)
        return zip_buffer.getvalue()

    async def test_import_success_with_json_and_proxy(self):
        # Prepare mock zip with session and json
        files = {
            "79991112233.session": b"fake session",
            "79991112233.json": json.dumps({
                "api_id": 123,
                "api_hash": "hash123",
                "device_model": "iPhone Test"
            })
        }
        zip_bytes = self.create_mock_zip(files)

        # Directus mocks
        # Deduplication check returns nothing (empty data)
        self.mock_directus.client.get.return_value.json.return_value = {"data": []}
        self.mock_directus.client.get.return_value.raise_for_status = MagicMock()
        
        # Create item returns success
        self.mock_directus.create_item.return_value = {"id": 10}
        
        # Proxy available
        self.mock_acquire_proxy.return_value = {"id": 5, "host": "1.1.1.1", "port": 8080, "type": "socks5"}

        # Run import
        results = await import_accounts_from_zip(
            zip_bytes=zip_bytes,
            filename="import.zip",
            auto_assign_proxy=True
        )

        # Assertions
        if results["imported"] != 1:
            print(f"DEBUG: Results: {results}")

        self.assertEqual(results["imported"], 1)
        self.assertEqual(len(results["errors"]), 0)
        self.assertEqual(results["accounts"][0]["phone"], "79991112233")
        self.assertTrue(results["accounts"][0]["proxy_assigned"])
        
        # Check API ID used (from JSON)
        self.mock_telegram_client_class.assert_called_with(unittest.mock.ANY, 123, "hash123", proxy={'proxy_type': 'socks5', 'addr': '1.1.1.1', 'port': 8080, 'rdns': True})
        
        # Check Directus storage call
        self.mock_directus.create_item.assert_called_once()
        args, kwargs = self.mock_directus.create_item.call_args
        data = args[1]
        self.assertEqual(data["phone"], "79991112233")
        self.assertEqual(data["device_info"]["device_model"], "iPhone Test")

    async def test_import_fallback_to_env(self):
        # Prepare mock zip WITHOUT json
        files = {
            "79995556677.session": b"fake session"
        }
        zip_bytes = self.create_mock_zip(files)

        self.mock_directus.client.get.return_value.json.return_value = {"data": []}
        self.mock_directus.create_item.return_value = {"id": 11}

        # Run import
        results = await import_accounts_from_zip(
            zip_bytes=zip_bytes,
            filename="import.zip",
            auto_assign_proxy=False
        )

        # Assertions
        self.assertEqual(results["imported"], 1)
        # Check API ID used (from ENV)
        # Check API ID used (from ENV)
        self.mock_telegram_client_class.assert_called_with(unittest.mock.ANY, 2222, "env_hash", proxy=None)

    async def test_import_fails_no_proxy(self):
        # Prepare mock zip
        files = {
            "79998889900.session": b"fake session"
        }
        zip_bytes = self.create_mock_zip(files)
        
        self.mock_acquire_proxy.return_value = None # No proxy available
        self.mock_directus.client.get.return_value.json.return_value = {"data": []}

        # Run import with auto_assign_proxy=True (default/mandatory)
        results = await import_accounts_from_zip(
            zip_bytes=zip_bytes,
            filename="import.zip",
            auto_assign_proxy=True
        )

        # Assertions
        self.assertEqual(results["imported"], 0)
        self.assertEqual(len(results["errors"]), 1)
        self.assertEqual(results["errors"][0]["error_code"], "NO_PROXY_AVAILABLE")

    async def test_import_duplicate_skipping(self):
        # Prepare mock zip
        files = {
            "79990000000.session": b"fake session"
        }
        zip_bytes = self.create_mock_zip(files)

        # Deduplication check returns existing user
        self.mock_response.json.return_value = {"data": [{"id": 1}]}

        # Run import
        results = await import_accounts_from_zip(
            zip_bytes=zip_bytes,
            filename="import.zip",
            auto_assign_proxy=False
        )

        # Assertions
        self.assertEqual(results["imported"], 0)
        self.assertEqual(len(results["errors"]), 1)
        self.assertEqual(results["errors"][0]["error_code"], "already_exists")

    async def test_import_invalid_session(self):
        # Prepare mock zip
        files = {
            "79991234567.session": b"fake session"
        }
        zip_bytes = self.create_mock_zip(files)

        self.mock_response.json.return_value = {"data": []}
        
        # Mock unauthorized session
        self.mock_client.is_user_authorized = AsyncMock(return_value=False)

        # Run import
        results = await import_accounts_from_zip(
            zip_bytes=zip_bytes,
            filename="import.zip",
            auto_assign_proxy=False
        )

        # Assertions
        self.assertEqual(results["imported"], 0)
        self.assertEqual(len(results["errors"]), 1)
        self.assertEqual(results["errors"][0]["error_code"], "invalid_session")

if __name__ == "__main__":
    unittest.main()
