"""
Telegram Client Factory

Single source of truth for Telethon client construction with mandatory proxy usage.
All Telegram connections must be created through this factory to ensure proxy routing.
"""

import logging
from typing import Dict, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


def map_proxy_type(directus_type: str) -> str:
    """
    Map Directus proxy type to Telethon proxy type string.
    
    Args:
        directus_type: Proxy type from Directus ('http', 'sock4', 'socks5')
        
    Returns:
        Telethon-compatible proxy type string
        
    Raises:
        ValueError: If proxy type is unknown
    """
    type_mapping = {
        'http': 'http',
        'sock4': 'socks4',  # Note: Directus uses 'sock4', Telethon expects 'socks4'
        'socks5': 'socks5'
    }
    
    normalized = directus_type.lower().strip()
    
    if normalized not in type_mapping:
        raise ValueError(
            f"Unknown proxy type: '{directus_type}'. "
            f"Supported types: {', '.join(type_mapping.keys())}"
        )
    
    return type_mapping[normalized]


def build_telethon_proxy(proxy_row: dict) -> dict:
    """
    Build Telethon proxy configuration dictionary from Directus proxy row.
    
    Args:
        proxy_row: Proxy data from Directus with fields: type, host, port, username, password
        
    Returns:
        Dictionary compatible with TelegramClient proxy parameter:
        {
            "proxy_type": str,  # 'http', 'socks4', or 'socks5'
            "addr": str,        # hostname or IP
            "port": int,        # port number
            "rdns": bool,       # always True for privacy
            "username": str,    # optional, only if present
            "password": str     # optional, only if present
        }
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Validate required fields
    if not proxy_row.get('host'):
        raise ValueError("Proxy missing required field: 'host'")
    if not proxy_row.get('port'):
        raise ValueError("Proxy missing required field: 'port'")
    if not proxy_row.get('type'):
        raise ValueError("Proxy missing required field: 'type'")
    
    # Map proxy type
    proxy_type = map_proxy_type(proxy_row['type'])
    
    # Build base configuration
    proxy_config = {
        "proxy_type": proxy_type,
        "addr": proxy_row['host'],
        "port": int(proxy_row['port']),
        "rdns": True  # Always use remote DNS for privacy
    }
    
    # Add credentials only if present and non-empty
    username = (proxy_row.get('username') or '').strip()
    password = (proxy_row.get('password') or '').strip()
    
    if username:
        proxy_config['username'] = username
    if password:
        proxy_config['password'] = password
    
    return proxy_config


def format_proxy(proxy_row: dict) -> str:
    """
    Format proxy for safe logging (without credentials).
    
    Args:
        proxy_row: Proxy data from Directus
        
    Returns:
        Formatted string: "type://host:port" (e.g., "socks5://proxy.example.com:1080")
    """
    proxy_type = proxy_row.get('type', 'unknown')
    host = proxy_row.get('host', 'unknown')
    port = proxy_row.get('port', '0')
    
    return f"{proxy_type}://{host}:{port}"


async def get_client_for_account(account: dict, directus) -> TelegramClient:
    """
    Create a TelegramClient for the given account with mandatory proxy.
    
    This is the single source of truth for Telethon client construction.
    All clients MUST be created through this factory to ensure proxy usage.
    
    Args:
        account: Account data from Directus with fields:
                 - session_string: Telegram session string
                 - api_id: Telegram API ID
                 - api_hash: Telegram API hash
                 - proxy_id: Either expanded proxy object or proxy ID (int)
        directus: DirectusClient instance for fetching proxy if needed
        force_proxy: Boolean to explicitly enforce proxy usage (default: True). 
                     Since this factory ALWAYS enforces proxies, this is mainly for semantic assertion.
        
    Returns:
        TelegramClient instance (not connected - caller must call connect())
        
    Raises:
        ValueError: If account is missing required fields or proxy
        RuntimeError: If proxy status is not active or proxy fetch fails
        
    Usage:
        ```python
        from backend.services.telegram_client_factory import get_client_for_account, format_proxy
        from backend.directus_client import directus
        
        # Get account with proxy
        account = await directus.client.get(
            f"/items/accounts/{account_id}",
            params={"fields": "id,phone,session_string,api_id,api_hash,proxy_id.*"}
        )
        account_data = account.json()['data']
        
        # Create client
        client = await get_client_for_account(account_data, directus)
        
        # Log before connecting (safe - no credentials)
        proxy = account_data.get('proxy_id')
        logger.info(f"Connecting account {account_data['id']} ({account_data['phone']}) via {format_proxy(proxy)}")
        
        # Connect and use
        await client.connect()
        try:
            # ... use client ...
        finally:
            await client.disconnect()
        ```
    """
    # Validate account has required fields
    if not account.get('session_string'):
        raise ValueError(f"Account {account.get('id', 'unknown')} missing session_string")
    
    if not account.get('api_id'):
        raise ValueError(f"Account {account.get('id', 'unknown')} missing api_id")
    
    if not account.get('api_hash'):
        raise ValueError(f"Account {account.get('id', 'unknown')} missing api_hash")
    
    # Get proxy - either expanded object or ID
    proxy = account.get('proxy_id')
    
    if not proxy:
        if force_proxy:
             raise ValueError(
                f"Account {account.get('id', 'unknown')} has no assigned proxy. "
                "All Telegram connections must use a proxy (strictly enforced)."
            )
        else:
             # NOTE: In this specific codebase, we generally don't allowed non-proxy connections.
             # But if force_proxy=False was passed, we might technically allow it if looking purely at this flag.
             # However, the factory docstring says "mandatory proxy". 
             # For safety, we will keep raising check unless explicitly relaxed logic is added later.
             # For now, we reuse the same error but maybe different wording if needed.
             raise ValueError(f"Account {account.get('id', 'unknown')} missing proxy (required).")
    
    # If proxy is just an ID (int), fetch the full proxy object
    if isinstance(proxy, int):
        logger.debug(f"Fetching proxy {proxy} from Directus for account {account.get('id')}")
        try:
            response = await directus.client.get(
                f"/items/proxies/{proxy}",
                params={"fields": "id,host,port,type,status,username,password"}
            )
            response.raise_for_status()
            proxy = response.json()['data']
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch proxy {proxy} for account {account.get('id', 'unknown')}: {e}"
            )
    
    # Validate proxy status is active
    proxy_status = proxy.get('status', '').lower()
    if proxy_status not in ('active', 'ok'):
        raise RuntimeError(
            f"Proxy {proxy.get('id', 'unknown')} for account {account.get('id', 'unknown')} "
            f"has invalid status: '{proxy_status}'. Expected 'active' or 'ok'."
        )
    
    # Build Telethon proxy configuration
    try:
        proxy_config = build_telethon_proxy(proxy)
    except ValueError as e:
        raise ValueError(
            f"Invalid proxy configuration for account {account.get('id', 'unknown')}: {e}"
        )
    
    # Create TelegramClient with proxy
    # Note: We do NOT call connect() - caller is responsible for connection lifecycle
    client = TelegramClient(
        StringSession(account['session_string']),
        int(account['api_id']),
        account['api_hash'],
        proxy=proxy_config
    )
    
    logger.debug(
        f"Created TelegramClient for account {account.get('id', 'unknown')} "
        f"with proxy {format_proxy(proxy)}"
    )
    
    return client


def get_client_from_config(telegram_config: dict, proxy_dict: Optional[dict] = None) -> TelegramClient:
    """
    Create a TelegramClient from local configuration with optional proxy.
    
    Args:
        telegram_config: Config dictionary with keys: session, api_id, api_hash
        proxy_dict: Optional proxy config: {type, host, port, username, password}
        
    Returns:
        TelegramClient instance
        
    Raises:
        ValueError: If config is invalid
    """
    if not telegram_config.get('session'):
        raise ValueError("Config missing 'session'")
    if not telegram_config.get('api_id'):
        raise ValueError("Config missing 'api_id'")
    if not telegram_config.get('api_hash'):
        raise ValueError("Config missing 'api_hash'")
        
    proxy_config = None
    if proxy_dict and proxy_dict.get('host'):
        # Validate and build proxy
        # Ensure 'type' exists, default to socks5 if missing (though build_telethon_proxy requires it)
        if not proxy_dict.get('type'):
            proxy_dict['type'] = 'socks5'
            
        try:
            proxy_config = build_telethon_proxy(proxy_dict)
        except ValueError as e:
            raise ValueError(f"Invalid proxy configuration: {e}")
        
    client = TelegramClient(
        telegram_config['session'],
        int(telegram_config['api_id']),
        telegram_config['api_hash'],
        proxy=proxy_config
    )
    
    logger.debug(
        f"Created TelegramClient from config with "
        f"{'proxy ' + format_proxy(proxy_dict) if proxy_config else 'NO PROXY (Warning: ensure strict proxy settings)'}"
    )
    
    return client
