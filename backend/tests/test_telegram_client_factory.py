"""
Unit tests for telegram_client_factory module.

These tests verify proxy type mapping, configuration building, and client creation
WITHOUT making actual network connections.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.telegram_client_factory import (
    map_proxy_type,
    build_telethon_proxy,
    format_proxy,
    get_client_for_account
)


class TestMapProxyType:
    """Test proxy type mapping from Directus to Telethon."""
    
    def test_map_http(self):
        """Test mapping 'http' type."""
        assert map_proxy_type('http') == 'http'
    
    def test_map_sock4(self):
        """Test mapping 'sock4' to 'socks4'."""
        assert map_proxy_type('sock4') == 'socks4'
    
    def test_map_socks5(self):
        """Test mapping 'socks5' type."""
        assert map_proxy_type('socks5') == 'socks5'
    
    def test_case_insensitive(self):
        """Test that mapping is case-insensitive."""
        assert map_proxy_type('HTTP') == 'http'
        assert map_proxy_type('SOCK4') == 'socks4'
        assert map_proxy_type('SoCkS5') == 'socks5'
    
    def test_whitespace_handling(self):
        """Test that whitespace is stripped."""
        assert map_proxy_type(' http ') == 'http'
        assert map_proxy_type('\tsock4\n') == 'socks4'
    
    def test_unknown_type_raises_error(self):
        """Test that unknown types raise ValueError."""
        with pytest.raises(ValueError, match="Unknown proxy type"):
            map_proxy_type('unknown')
        
        with pytest.raises(ValueError, match="Unknown proxy type"):
            map_proxy_type('socks4a')


class TestBuildTelethonProxy:
    """Test Telethon proxy configuration building."""
    
    def test_build_with_credentials(self):
        """Test building proxy config with username and password."""
        proxy_row = {
            'type': 'socks5',
            'host': 'proxy.example.com',
            'port': 1080,
            'username': 'user123',
            'password': 'pass456'
        }
        
        result = build_telethon_proxy(proxy_row)
        
        assert result == {
            'proxy_type': 'socks5',
            'addr': 'proxy.example.com',
            'port': 1080,
            'rdns': True,
            'username': 'user123',
            'password': 'pass456'
        }
    
    def test_build_without_credentials(self):
        """Test building proxy config without credentials."""
        proxy_row = {
            'type': 'http',
            'host': '192.168.1.100',
            'port': 8080
        }
        
        result = build_telethon_proxy(proxy_row)
        
        assert result == {
            'proxy_type': 'http',
            'addr': '192.168.1.100',
            'port': 8080,
            'rdns': True
        }
        assert 'username' not in result
        assert 'password' not in result
    
    def test_build_with_empty_credentials(self):
        """Test that empty string credentials are not included."""
        proxy_row = {
            'type': 'sock4',
            'host': 'proxy.test',
            'port': 9050,
            'username': '',
            'password': '   '  # Whitespace only
        }
        
        result = build_telethon_proxy(proxy_row)
        
        assert 'username' not in result
        assert 'password' not in result
    
    def test_build_with_only_username(self):
        """Test building with username but no password."""
        proxy_row = {
            'type': 'socks5',
            'host': 'proxy.test',
            'port': 1080,
            'username': 'user',
            'password': ''
        }
        
        result = build_telethon_proxy(proxy_row)
        
        assert result['username'] == 'user'
        assert 'password' not in result
    
    def test_port_conversion_to_int(self):
        """Test that port is converted to integer."""
        proxy_row = {
            'type': 'http',
            'host': 'proxy.test',
            'port': '8080'  # String port
        }
        
        result = build_telethon_proxy(proxy_row)
        
        assert result['port'] == 8080
        assert isinstance(result['port'], int)
    
    def test_missing_host_raises_error(self):
        """Test that missing host raises ValueError."""
        proxy_row = {
            'type': 'socks5',
            'port': 1080
        }
        
        with pytest.raises(ValueError, match="missing required field: 'host'"):
            build_telethon_proxy(proxy_row)
    
    def test_missing_port_raises_error(self):
        """Test that missing port raises ValueError."""
        proxy_row = {
            'type': 'socks5',
            'host': 'proxy.test'
        }
        
        with pytest.raises(ValueError, match="missing required field: 'port'"):
            build_telethon_proxy(proxy_row)
    
    def test_missing_type_raises_error(self):
        """Test that missing type raises ValueError."""
        proxy_row = {
            'host': 'proxy.test',
            'port': 1080
        }
        
        with pytest.raises(ValueError, match="missing required field: 'type'"):
            build_telethon_proxy(proxy_row)
    
    def test_invalid_type_raises_error(self):
        """Test that invalid proxy type raises ValueError."""
        proxy_row = {
            'type': 'invalid',
            'host': 'proxy.test',
            'port': 1080
        }
        
        with pytest.raises(ValueError, match="Unknown proxy type"):
            build_telethon_proxy(proxy_row)


class TestFormatProxy:
    """Test proxy formatting for safe logging."""
    
    def test_format_basic(self):
        """Test basic proxy formatting."""
        proxy_row = {
            'type': 'socks5',
            'host': 'proxy.example.com',
            'port': 1080
        }
        
        result = format_proxy(proxy_row)
        
        assert result == 'socks5://proxy.example.com:1080'
    
    def test_format_with_credentials_not_shown(self):
        """Test that credentials are NOT included in formatted output."""
        proxy_row = {
            'type': 'http',
            'host': '192.168.1.100',
            'port': 8080,
            'username': 'secret_user',
            'password': 'secret_pass'
        }
        
        result = format_proxy(proxy_row)
        
        assert result == 'http://192.168.1.100:8080'
        assert 'secret_user' not in result
        assert 'secret_pass' not in result
    
    def test_format_with_missing_fields(self):
        """Test formatting with missing fields (graceful degradation)."""
        proxy_row = {}
        
        result = format_proxy(proxy_row)
        
        assert result == 'unknown://unknown:0'


@pytest.mark.asyncio
class TestGetClientForAccount:
    """Test main factory function for creating Telegram clients."""
    
    async def test_create_client_with_expanded_proxy(self):
        """Test creating client when proxy is already expanded."""
        account = {
            'id': 123,
            'phone': '+1234567890',
            'session_string': 'test_session_string',
            'api_id': 12345,
            'api_hash': 'test_api_hash',
            'proxy_id': {
                'id': 1,
                'type': 'socks5',
                'host': 'proxy.test',
                'port': 1080,
                'status': 'active',
                'username': 'user',
                'password': 'pass'
            }
        }
        
        directus = MagicMock()
        
        with patch('backend.services.telegram_client_factory.TelegramClient') as mock_client:
            client = await get_client_for_account(account, directus)
            
            # Verify TelegramClient was called with correct arguments
            mock_client.assert_called_once()
            call_args = mock_client.call_args
            
            # Check session string
            assert call_args[0][1] == 12345  # api_id
            assert call_args[0][2] == 'test_api_hash'  # api_hash
            
            # Check proxy configuration
            proxy_config = call_args[1]['proxy']
            assert proxy_config['proxy_type'] == 'socks5'
            assert proxy_config['addr'] == 'proxy.test'
            assert proxy_config['port'] == 1080
            assert proxy_config['username'] == 'user'
            assert proxy_config['password'] == 'pass'
    
    async def test_create_client_with_proxy_id_fetch(self):
        """Test creating client when proxy needs to be fetched."""
        account = {
            'id': 123,
            'session_string': 'test_session',
            'api_id': 12345,
            'api_hash': 'test_hash',
            'proxy_id': 42  # Just an ID, not expanded
        }
        
        # Mock Directus client
        directus = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            'data': {
                'id': 42,
                'type': 'http',
                'host': 'fetched.proxy',
                'port': 8080,
                'status': 'ok'
            }
        }
        directus.client.get = AsyncMock(return_value=mock_response)
        
        with patch('backend.services.telegram_client_factory.TelegramClient') as mock_client:
            client = await get_client_for_account(account, directus)
            
            # Verify proxy was fetched
            directus.client.get.assert_called_once()
            call_args = directus.client.get.call_args
            assert '/items/proxies/42' in call_args[0][0]
            
            # Verify client was created with fetched proxy
            proxy_config = mock_client.call_args[1]['proxy']
            assert proxy_config['addr'] == 'fetched.proxy'
    
    async def test_missing_session_string_raises_error(self):
        """Test that missing session_string raises ValueError."""
        account = {
            'id': 123,
            'api_id': 12345,
            'api_hash': 'test_hash',
            'proxy_id': {'type': 'socks5', 'host': 'proxy', 'port': 1080, 'status': 'active'}
        }
        
        directus = MagicMock()
        
        with pytest.raises(ValueError, match="missing session_string"):
            await get_client_for_account(account, directus)
    
    async def test_missing_api_id_raises_error(self):
        """Test that missing api_id raises ValueError."""
        account = {
            'id': 123,
            'session_string': 'test',
            'api_hash': 'test_hash',
            'proxy_id': {'type': 'socks5', 'host': 'proxy', 'port': 1080, 'status': 'active'}
        }
        
        directus = MagicMock()
        
        with pytest.raises(ValueError, match="missing api_id"):
            await get_client_for_account(account, directus)
    
    async def test_missing_proxy_raises_error(self):
        """Test that missing proxy raises ValueError."""
        account = {
            'id': 123,
            'session_string': 'test',
            'api_id': 12345,
            'api_hash': 'test_hash'
            # No proxy_id
        }
        
        directus = MagicMock()
        
        with pytest.raises(ValueError, match="no assigned proxy"):
            await get_client_for_account(account, directus)
    
    async def test_inactive_proxy_raises_error(self):
        """Test that inactive proxy status raises RuntimeError."""
        account = {
            'id': 123,
            'session_string': 'test',
            'api_id': 12345,
            'api_hash': 'test_hash',
            'proxy_id': {
                'id': 1,
                'type': 'socks5',
                'host': 'proxy.test',
                'port': 1080,
                'status': 'failed'  # Not active!
            }
        }
        
        directus = MagicMock()
        
        with pytest.raises(RuntimeError, match="invalid status: 'failed'"):
            await get_client_for_account(account, directus)
    
    async def test_proxy_fetch_failure_raises_error(self):
        """Test that proxy fetch failure raises RuntimeError."""
        account = {
            'id': 123,
            'session_string': 'test',
            'api_id': 12345,
            'api_hash': 'test_hash',
            'proxy_id': 42
        }
        
        directus = MagicMock()
        directus.client.get = AsyncMock(side_effect=Exception("Network error"))
        
        with pytest.raises(RuntimeError, match="Failed to fetch proxy"):
            await get_client_for_account(account, directus)
