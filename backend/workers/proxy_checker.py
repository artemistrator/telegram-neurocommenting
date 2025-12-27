"""
Proxy Health Checker Worker
Regularly checks all proxies (active, ok, dead) and updates their status.
If a proxy is dead, marks linked accounts as proxy_unavailable=True.
If a proxy recovers, marks linked accounts as proxy_unavailable=False.
"""

import asyncio
import os
import sys
import logging
import time
import socket
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.directus_client import DirectusClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CHECK_INTERVAL = int(os.getenv("PROXY_CHECK_INTERVAL_SECONDS", "900")) # 15 minutes default
TCP_TIMEOUT = 3.0

directus = DirectusClient()

async def check_proxy_tcp(host: str, port: int) -> bool:
    """
    Check if proxy port is open via TCP.
    """
    try:
        # Use asyncio.open_connection for async TCP check
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), 
                timeout=TCP_TIMEOUT
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False
    except Exception as e:
        logger.debug(f"TCP check error for {host}:{port}: {e}")
        return False

async def update_proxy_status(proxy: dict, is_alive: bool, error_msg: str = None):
    """
    Update proxy status and propagate to accounts.
    """
    proxy_id = proxy['id']
    current_status = proxy.get('status')
    
    update_data = {
        "last_check": datetime.now().isoformat()
    }
    
    # Logic for status update
    new_status = current_status
    if is_alive:
        # If was dead or unknown, set to active. If was ok, leave as ok.
        if current_status not in ['active', 'ok']:
            new_status = 'active'
        update_data['last_error'] = None # Clear error
    else:
        new_status = 'dead'
        update_data['last_error'] = error_msg or "TCP Connect Timeout"

    if new_status != current_status:
        update_data['status'] = new_status
        logger.info(f"Proxy {proxy_id} status changed: {current_status} -> {new_status}")
    
    # Update Proxy
    try:
        await directus.update_item("proxies", proxy_id, update_data)
    except Exception as e:
        logger.error(f"Failed to update proxy {proxy_id}: {e}")
        return

    # Propagation to Accounts
    # Only if status changed between alive/dead state
    was_alive = current_status in ['active', 'ok']
    now_alive = new_status in ['active', 'ok']
    
    if was_alive != now_alive:
        # Find accounts linked to this proxy
        try:
            resp = await directus.safe_get("/items/accounts", params={
                "filter[proxy_id][_eq]": proxy_id,
                "fields": "id"
            })
            accounts = resp.json().get('data', [])
            
            for acc in accounts:
                # If now dead -> unavailable=True
                # If now alive -> unavailable=False
                unavailable = not now_alive
                await directus.update_item("accounts", acc['id'], {
                    "proxy_unavailable": unavailable
                })
                logger.info(f"Account {acc['id']} proxy_unavailable set to {unavailable}")
                
        except Exception as e:
            logger.error(f"Failed to propagate status to accounts for proxy {proxy_id}: {e}")

async def run_checker():
    """
    Main checker loop.
    """
    logger.info(f"Starting Proxy Checker (Interval: {CHECK_INTERVAL}s)")
    
    # Ensure Directus login
    if not directus.token:
        await directus.login()

    while True:
        try:
            logger.info("Starting check cycle...")
            start_time = time.time()
            
            # Fetch all monitored proxies
            params = {
                "filter[status][_in]": "active,ok,dead",
                "limit": -1,
                "fields": "id,host,port,status,type"
            }
            
            resp = await directus.safe_get("/items/proxies", params=params)
            proxies = resp.json().get('data', [])
            
            logger.info(f"Checking {len(proxies)} proxies...")
            
            for proxy in proxies:
                host = proxy.get('host')
                port = proxy.get('port')
                
                if not host or not port:
                    continue
                    
                is_alive = await check_proxy_tcp(host, int(port))
                await update_proxy_status(proxy, is_alive)
            
            elapsed = time.time() - start_time
            logger.info(f"Check cycle completed in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Error in checker cycle: {e}")
            
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_checker())
    except KeyboardInterrupt:
        logger.info("Proxy Checker stopped")
