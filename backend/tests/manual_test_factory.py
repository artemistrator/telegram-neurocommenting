"""
Manual test script for telegram_client_factory module.
Run this to verify the factory functions work correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.telegram_client_factory import (
    map_proxy_type,
    build_telethon_proxy,
    format_proxy
)


def test_map_proxy_type():
    """Test proxy type mapping."""
    print("Testing map_proxy_type()...")
    
    # Test valid types
    assert map_proxy_type('http') == 'http', "http mapping failed"
    assert map_proxy_type('sock4') == 'socks4', "sock4 mapping failed"
    assert map_proxy_type('socks5') == 'socks5', "socks5 mapping failed"
    
    # Test case insensitivity
    assert map_proxy_type('HTTP') == 'http', "case insensitivity failed"
    assert map_proxy_type('SOCK4') == 'socks4', "case insensitivity failed"
    
    # Test invalid type
    try:
        map_proxy_type('invalid')
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown proxy type" in str(e)
    
    print("✓ map_proxy_type() tests passed")


def test_build_telethon_proxy():
    """Test Telethon proxy configuration building."""
    print("\nTesting build_telethon_proxy()...")
    
    # Test with credentials
    proxy_with_creds = {
        'type': 'socks5',
        'host': 'proxy.example.com',
        'port': 1080,
        'username': 'user123',
        'password': 'pass456'
    }
    
    result = build_telethon_proxy(proxy_with_creds)
    assert result['proxy_type'] == 'socks5'
    assert result['addr'] == 'proxy.example.com'
    assert result['port'] == 1080
    assert result['rdns'] == True
    assert result['username'] == 'user123'
    assert result['password'] == 'pass456'
    print("  ✓ Proxy with credentials")
    
    # Test without credentials
    proxy_no_creds = {
        'type': 'http',
        'host': '192.168.1.100',
        'port': 8080
    }
    
    result = build_telethon_proxy(proxy_no_creds)
    assert result['proxy_type'] == 'http'
    assert 'username' not in result
    assert 'password' not in result
    print("  ✓ Proxy without credentials")
    
    # Test sock4 mapping
    proxy_sock4 = {
        'type': 'sock4',
        'host': 'proxy.test',
        'port': 9050
    }
    
    result = build_telethon_proxy(proxy_sock4)
    assert result['proxy_type'] == 'socks4'
    print("  ✓ sock4 -> socks4 mapping")
    
    # Test missing host
    try:
        build_telethon_proxy({'type': 'socks5', 'port': 1080})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "missing required field: 'host'" in str(e)
    print("  ✓ Missing host validation")
    
    print("✓ build_telethon_proxy() tests passed")


def test_format_proxy():
    """Test proxy formatting for safe logging."""
    print("\nTesting format_proxy()...")
    
    # Test basic formatting
    proxy = {
        'type': 'socks5',
        'host': 'proxy.example.com',
        'port': 1080
    }
    
    result = format_proxy(proxy)
    assert result == 'socks5://proxy.example.com:1080'
    print("  ✓ Basic formatting")
    
    # Test that credentials are NOT shown
    proxy_with_creds = {
        'type': 'http',
        'host': '192.168.1.100',
        'port': 8080,
        'username': 'secret_user',
        'password': 'secret_pass'
    }
    
    result = format_proxy(proxy_with_creds)
    assert result == 'http://192.168.1.100:8080'
    assert 'secret_user' not in result
    assert 'secret_pass' not in result
    print("  ✓ Credentials not shown in output")
    
    print("✓ format_proxy() tests passed")


if __name__ == '__main__':
    print("=" * 60)
    print("Running telegram_client_factory manual tests")
    print("=" * 60)
    
    try:
        test_map_proxy_type()
        test_build_telethon_proxy()
        test_format_proxy()
        
        print("\n" + "=" * 60)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
