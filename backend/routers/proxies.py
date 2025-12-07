import re
import time
import asyncio
import socks
import socket
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Form
from pydantic import BaseModel
import logging

from backend.directus_client import directus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proxies", tags=["proxies"])


# Pydantic models
class ProxyImportResponse(BaseModel):
    imported: int
    errors: List[str]


class ProxyItem(BaseModel):
    id: int
    host: str
    port: int
    type: str
    status: Optional[str] = None
    assigned_to: Optional[str] = None


class ProxyTestResponse(BaseModel):
    status: str
    ping_ms: Optional[int] = None


# Helper functions
def parse_proxy_line(line: str, default_type: str = 'socks5') -> Optional[Dict[str, str]]:
    """
    Parse proxy string in various formats:
    - socks5://user:pass@host:port
    - host:port:user:pass
    - host:port
    
    Args:
        line: Proxy string to parse
        default_type: Default proxy type if not specified in line (socks5, socks4, http)
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Format: socks5://user:pass@host:port or socks5://host:port
    url_pattern = r'^(socks5|socks4|http)://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$'
    match = re.match(url_pattern, line)
    if match:
        proxy_type, username, password, host, port = match.groups()
        return {
            'type': proxy_type,
            'host': host,
            'port': int(port),
            'username': username or '',
            'password': password or ''
        }
    
    # Format: host:port:user:pass or host:port (use default_type)
    parts = line.split(':')
    if len(parts) == 4:
        return {
            'type': default_type,
            'host': parts[0],
            'port': int(parts[1]),
            'username': parts[2],
            'password': parts[3]
        }
    elif len(parts) == 2:
        return {
            'type': default_type,
            'host': parts[0],
            'port': int(parts[1]),
            'username': '',
            'password': ''
        }
    
    return None


async def test_proxy_connection(proxy_config: Dict) -> Dict:
    """
    Test proxy by connecting to telegram.org:443
    Returns status and ping time in milliseconds
    """
    try:
        # Map proxy type to socks module constants
        proxy_type_map = {
            'socks5': socks.SOCKS5,
            'socks4': socks.SOCKS4,
            'http': socks.HTTP
        }
        
        proxy_type = proxy_type_map.get(proxy_config['type'], socks.SOCKS5)
        
        # Create socket with proxy
        sock = socks.socksocket()
        sock.set_proxy(
            proxy_type=proxy_type,
            addr=proxy_config['host'],
            port=proxy_config['port'],
            username=proxy_config.get('username') or None,
            password=proxy_config.get('password') or None
        )
        
        # Set timeout
        sock.settimeout(10)
        
        # Measure connection time
        start_time = time.time()
        
        # Try to connect to Telegram
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: sock.connect(('telegram.org', 443))
        )
        
        end_time = time.time()
        ping_ms = int((end_time - start_time) * 1000)
        
        sock.close()
        
        return {
            'status': 'ok',
            'ping_ms': ping_ms
        }
        
    except Exception as e:
        logger.error(f"Proxy test failed: {e}")
        return {
            'status': 'failed',
            'ping_ms': None,
            'error': str(e)
        }


# API Endpoints

@router.post("/import", response_model=ProxyImportResponse)
async def import_proxies(
    file: UploadFile = File(...),
    default_type: str = Query('socks5', regex='^(socks5|socks4|http)$')
):
    """
    Import proxies from text/CSV file
    Supports formats:
    - socks5://user:pass@host:port
    - host:port:user:pass
    - host:port
    
    Args:
        file: Text file with proxy list
        default_type: Default proxy type for entries without explicit protocol (socks5, socks4, http)
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Read file content
        content = await file.read()
        text = content.decode('utf-8')
        
        lines = text.split('\n')
        imported = 0
        errors = []
        
        for line_num, line in enumerate(lines, 1):
            try:
                proxy_data = parse_proxy_line(line, default_type=default_type)
                
                if not proxy_data:
                    continue  # Skip empty lines and comments
                
                # Create proxy record in Directus
                # Note: user_created will be set automatically by Directus based on auth token
                await directus.client.post("/items/proxies", json={
                    'host': proxy_data['host'],
                    'port': proxy_data['port'],
                    'type': proxy_data['type'],
                    'username': proxy_data.get('username', ''),
                    'password': proxy_data.get('password', ''),
                    'status': 'untested'
                })
                
                imported += 1
                logger.info(f"Imported proxy: {proxy_data['host']}:{proxy_data['port']} ({proxy_data['type']})")
                
            except Exception as e:
                error_msg = f"Line {line_num}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            'imported': imported,
            'errors': errors
        }
        
    except Exception as e:
        logger.error(f"Error importing proxies: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/list")
async def list_proxies():
    """
    Get list of proxies for current user
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Get proxies from Directus
        # Filter by current user (Directus will handle this based on auth token)
        response = await directus.client.get("/items/proxies", params={
            "fields": "id,host,port,type,status,assigned_to,username",
            "sort": "-date_created"
        })
        
        response.raise_for_status()
        data = response.json()
        
        proxies = data.get('data', [])
        
        return {
            'proxies': proxies,
            'total': len(proxies)
        }
        
    except Exception as e:
        logger.error(f"Error listing proxies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list proxies: {str(e)}")


@router.post("/test/{proxy_id}", response_model=ProxyTestResponse)
async def test_proxy(proxy_id: int):
    """
    Test proxy connection to telegram.org:443
    Updates status and last_check fields
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Get proxy details
        response = await directus.client.get(f"/items/proxies/{proxy_id}")
        response.raise_for_status()
        proxy = response.json()['data']
        
        # Test connection
        test_result = await test_proxy_connection({
            'type': proxy['type'],
            'host': proxy['host'],
            'port': proxy['port'],
            'username': proxy.get('username', ''),
            'password': proxy.get('password', '')
        })
        
        # Update proxy status in Directus
        update_data = {
            'status': test_result['status'],
            'last_check': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if test_result.get('ping_ms'):
            update_data['ping_ms'] = test_result['ping_ms']
        
        await directus.update_item("proxies", proxy_id, update_data)
        
        logger.info(f"Proxy {proxy_id} test result: {test_result['status']}")
        
        return {
            'status': test_result['status'],
            'ping_ms': test_result.get('ping_ms')
        }
        
    except Exception as e:
        logger.error(f"Error testing proxy {proxy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy test failed: {str(e)}")


@router.patch("/{proxy_id}")
async def update_proxy(proxy_id: int, data: dict):
    """
    Update proxy fields (type, status, etc.)
    When type is changed, status is automatically reset to 'untested'
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # If type is being changed, reset status to untested
        if 'type' in data:
            data['status'] = 'untested'
            data['ping_ms'] = None
            logger.info(f"Proxy {proxy_id} type changed to {data['type']}, status reset to untested")
        
        # Update proxy in Directus
        response = await directus.client.patch(f"/items/proxies/{proxy_id}", json=data)
        response.raise_for_status()
        updated_proxy = response.json()['data']
        
        logger.info(f"Updated proxy {proxy_id}")
        
        return {
            'status': 'success',
            'proxy': updated_proxy
        }
        
    except Exception as e:
        logger.error(f"Error updating proxy {proxy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update proxy: {str(e)}")


@router.delete("/{proxy_id}")
async def delete_proxy(proxy_id: int):
    """
    Delete proxy by ID
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Delete proxy from Directus
        response = await directus.client.delete(f"/items/proxies/{proxy_id}")
        response.raise_for_status()
        
        logger.info(f"Deleted proxy {proxy_id}")
        
        return {
            'status': 'success',
            'message': f'Proxy {proxy_id} deleted'
        }
        
    except Exception as e:
        logger.error(f"Error deleting proxy {proxy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete proxy: {str(e)}")
