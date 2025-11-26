import asyncio
import json
import os
import csv
import shutil
from datetime import datetime
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.sessions import MemorySession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
import time
import socket
import socks

ACCOUNTS_FILE = 'accounts.json'
SESSIONS_DIR = 'sessions'

class AccountManager:
    def __init__(self):
        self.accounts = []
        self.load_accounts()
        
        # Create sessions directory if not exists
        if not os.path.exists(SESSIONS_DIR):
            os.makedirs(SESSIONS_DIR)
    
    def load_accounts(self):
        """Load accounts from accounts.json"""
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.accounts = data.get('accounts', [])
            except Exception as e:
                print(f"Error loading accounts: {e}")
                self.accounts = []
        else:
            self.accounts = []
    
    def save_accounts(self):
        """Save accounts to accounts.json"""
        try:
            with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'accounts': self.accounts}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving accounts: {e}")
            raise
    
    def get_next_id(self) -> int:
        """Get next available account ID"""
        if not self.accounts:
            return 1
        return max(acc['id'] for acc in self.accounts) + 1
    
    async def import_from_csv(self, csv_content: str, session_files: Dict[str, bytes]) -> Dict:
        """
        Import accounts from CSV and session files
        
        Args:
            csv_content: CSV file content as string
            session_files: Dict of {filename: file_bytes}
        
        Returns:
            Dict with import results
        """
        imported = 0
        errors = []
        
        try:
            # Parse CSV
            csv_reader = csv.DictReader(csv_content.splitlines())
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start from 2 (header is 1)
                try:
                    phone = row.get('phone', '').strip()
                    api_id = row.get('api_id', '').strip()
                    api_hash = row.get('api_hash', '').strip()
                    session_file = row.get('session_file', '').strip()
                    
                    # Validate required fields
                    if not all([phone, api_id, api_hash, session_file]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Check if session file exists in uploaded files
                    if session_file not in session_files:
                        errors.append(f"Row {row_num}: Session file '{session_file}' not found")
                        continue
                    
                    # Parse proxy if provided
                    proxy = None
                    if row.get('proxy_host'):
                        proxy = {
                            'type': row.get('proxy_type', 'socks5'),
                            'host': row.get('proxy_host'),
                            'port': int(row.get('proxy_port', 1080)),
                            'username': row.get('proxy_user', ''),
                            'password': row.get('proxy_pass', ''),
                            'status': 'unknown'
                        }
                    
                    # Save session file
                    session_path = os.path.join(SESSIONS_DIR, session_file)
                    with open(session_path, 'wb') as f:
                        f.write(session_files[session_file])
                    
                    # Create account entry
                    account = {
                        'id': self.get_next_id(),
                        'phone': phone,
                        'api_id': api_id,
                        'api_hash': api_hash,
                        'session_file': session_path,
                        'proxy': proxy,
                        'status': 'active',
                        'created_at': datetime.now().isoformat(),
                        'last_active': None,
                        'stats': {
                            'comments_posted': 0,
                            'tokens_used': 0
                        }
                    }
                    
                    self.accounts.append(account)
                    imported += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            # Save accounts
            if imported > 0:
                self.save_accounts()
            
            return {
                'imported': imported,
                'errors': errors,
                'total': imported + len(errors)
            }
            
        except Exception as e:
            raise Exception(f"CSV parsing error: {str(e)}")
    
    async def test_proxy(self, proxy_config: Dict) -> Dict:
        """
        Test proxy connection to Telegram
        
        Args:
            proxy_config: {type, host, port, username, password}
        
        Returns:
            {status: 'ok'/'failed', ping_ms: int, error: str}
        """
        client = None
        try:
            # Map proxy type string to socks constant
            proxy_type_map = {
                'socks5': socks.SOCKS5,
                'socks4': socks.SOCKS4,
                'http': socks.HTTP
            }
            
            proxy_type_str = proxy_config.get('type', 'socks5').lower()
            proxy_type_const = proxy_type_map.get(proxy_type_str, socks.SOCKS5)
            
            # Strict proxy check - test socket connection first
            try:
                s = socks.socksocket()
                s.set_proxy(
                    proxy_type_const,
                    proxy_config['host'],
                    int(proxy_config['port']),
                    username=proxy_config.get('username'),
                    password=proxy_config.get('password')
                )
                s.settimeout(5)
                s.connect(("telegram.org", 443))
                s.close()
            except Exception as e:
                return {
                    'status': 'failed',
                    'error': f'Proxy unreachable: {str(e)}'
                }
            
            # Create temporary client with proxy using in-memory session
            proxy = (
                proxy_config['type'],
                proxy_config['host'],
                int(proxy_config['port']),
                True,  # rdns
                proxy_config.get('username'),
                proxy_config.get('password')
            )
            
            # Use in-memory session to avoid database lock
            # Use dummy credentials for connection test
            client = TelegramClient(
                MemorySession(),
                api_id=1,  # Dummy
                api_hash='test',  # Dummy
                proxy=proxy
            )
            
            start_time = time.time()
            
            try:
                await asyncio.wait_for(client.connect(), timeout=10)
                ping_ms = int((time.time() - start_time) * 1000)
                
                return {
                    'status': 'ok',
                    'ping_ms': ping_ms
                }
                
            except asyncio.TimeoutError:
                return {
                    'status': 'failed',
                    'error': 'Connection timeout (10s)'
                }
                
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
        finally:
            # Always disconnect and cleanup
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    
    async def start_auth(self, api_id: int, api_hash: str, phone: str, proxy: Optional[Dict] = None) -> Dict:
        """
        Start authentication process - send code to Telegram
        
        Returns:
            {status: 'code_sent', account_id: int}
        """
        try:
            account_id = self.get_next_id()
            session_name = f"account_{phone.replace('+', '')}"
            session_path = os.path.join(SESSIONS_DIR, f"{session_name}.session")
            
            # Prepare proxy if provided
            proxy_tuple = None
            if proxy:
                proxy_tuple = (
                    proxy['type'],
                    proxy['host'],
                    int(proxy['port']),
                    True,
                    proxy.get('username'),
                    proxy.get('password')
                )
            
            # Create client
            client = TelegramClient(
                session_path.replace('.session', ''),
                int(api_id),
                api_hash,
                proxy=proxy_tuple
            )
            
            await client.connect()
            
            # Send code
            await client.send_code_request(phone)
            
            # Store temporary auth data
            temp_account = {
                'id': account_id,
                'phone': phone,
                'api_id': str(api_id),
                'api_hash': api_hash,
                'session_file': session_path,
                'proxy': proxy,
                'client': client,  # Keep client for next steps
                'status': 'pending_code'
            }
            
            # Store in memory (not in accounts list yet)
            if not hasattr(self, 'pending_auths'):
                self.pending_auths = {}
            self.pending_auths[account_id] = temp_account
            
            return {
                'status': 'code_sent',
                'account_id': account_id
            }
            
        except FloodWaitError as e:
            return {
                'status': 'flood_wait',
                'wait_seconds': e.seconds
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def submit_code(self, account_id: int, code: str) -> Dict:
        """
        Submit SMS code for authentication
        
        Returns:
            {status: 'success'/'need_2fa'/'error'}
        """
        try:
            if not hasattr(self, 'pending_auths') or account_id not in self.pending_auths:
                return {'status': 'error', 'error': 'Auth session not found'}
            
            temp_account = self.pending_auths[account_id]
            client = temp_account['client']
            
            try:
                await client.sign_in(temp_account['phone'], code)
                
                # Success - save account
                me = await client.get_me()
                
                account = {
                    'id': temp_account['id'],
                    'phone': temp_account['phone'],
                    'api_id': temp_account['api_id'],
                    'api_hash': temp_account['api_hash'],
                    'session_file': temp_account['session_file'],
                    'proxy': temp_account['proxy'],
                    'status': 'active',
                    'created_at': datetime.now().isoformat(),
                    'last_active': datetime.now().isoformat(),
                    'stats': {
                        'comments_posted': 0,
                        'tokens_used': 0
                    },
                    'user_info': {
                        'first_name': me.first_name,
                        'last_name': me.last_name,
                        'username': me.username
                    }
                }
                
                self.accounts.append(account)
                self.save_accounts()
                
                await client.disconnect()
                del self.pending_auths[account_id]
                
                return {'status': 'success', 'account': account}
                
            except SessionPasswordNeededError:
                # Need 2FA password
                temp_account['status'] = 'pending_2fa'
                return {'status': 'need_2fa'}
                
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def submit_password(self, account_id: int, password: str) -> Dict:
        """
        Submit 2FA password for authentication
        
        Returns:
            {status: 'success'/'error'}
        """
        try:
            if not hasattr(self, 'pending_auths') or account_id not in self.pending_auths:
                return {'status': 'error', 'error': 'Auth session not found'}
            
            temp_account = self.pending_auths[account_id]
            client = temp_account['client']
            
            await client.sign_in(password=password)
            
            # Success - save account
            me = await client.get_me()
            
            account = {
                'id': temp_account['id'],
                'phone': temp_account['phone'],
                'api_id': temp_account['api_id'],
                'api_hash': temp_account['api_hash'],
                'session_file': temp_account['session_file'],
                'proxy': temp_account['proxy'],
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'stats': {
                    'comments_posted': 0,
                    'tokens_used': 0
                },
                'user_info': {
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'username': me.username
                }
            }
            
            self.accounts.append(account)
            self.save_accounts()
            
            await client.disconnect()
            del self.pending_auths[account_id]
            
            return {'status': 'success', 'account': account}
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def get_accounts_list(self, mask_sensitive: bool = True) -> List[Dict]:
        """
        Get list of accounts with optional data masking
        """
        if not mask_sensitive:
            return self.accounts
        
        # Mask sensitive data
        masked_accounts = []
        for acc in self.accounts:
            masked = acc.copy()
            
            # Mask phone
            phone = acc['phone']
            if len(phone) > 7:
                masked['phone'] = phone[:5] + '****' + phone[-3:]
            
            # Mask api_hash
            api_hash = acc['api_hash']
            if len(api_hash) > 8:
                masked['api_hash'] = api_hash[:6] + '******' + api_hash[-4:]
            
            # Mask proxy password
            if acc.get('proxy') and acc['proxy'].get('password'):
                masked['proxy'] = acc['proxy'].copy()
                masked['proxy']['password'] = '****'
            
            masked_accounts.append(masked)
        
        return masked_accounts
    
    async def delete_account(self, account_id: int) -> bool:
        """
        Delete account and its session file
        """
        try:
            account = next((acc for acc in self.accounts if acc['id'] == account_id), None)
            if not account:
                return False
            
            # Delete session file
            if os.path.exists(account['session_file']):
                os.remove(account['session_file'])
            
            # Remove from list
            self.accounts = [acc for acc in self.accounts if acc['id'] != account_id]
            self.save_accounts()
            
            return True
            
        except Exception as e:
            print(f"Error deleting account: {e}")
            return False
