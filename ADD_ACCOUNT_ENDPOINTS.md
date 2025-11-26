# ============================================================
# ИНСТРУКЦИЯ: Добавление Account Management API в main.py
# ============================================================

# ШАГ 1: Добавить импорты (строка 6)
# ------------------------------------------------------------
# Найти:
from fastapi import FastAPI, HTTPException, BackgroundTasks

# Заменить на:
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File

# ШАГ 2: Добавить импорт AccountManager (после строки 13)
# ------------------------------------------------------------
# Найти:
import sys

# Добавить после:
from account_manager import AccountManager

# ШАГ 3: Добавить экземпляр AccountManager (после строки 29)
# ------------------------------------------------------------
# Найти:
event_log: List[Dict] = []

# Добавить после:
account_mgr = AccountManager()

# ШАГ 4: Добавить все API endpoints (перед строкой 597 "if __name__ == '__main__':")
# ------------------------------------------------------------
# Вставить весь этот блок:

# ============================================
# ACCOUNT MANAGEMENT API ENDPOINTS
# ============================================

@app.post("/api/accounts/import-csv")
async def import_accounts_csv(
    csv_file: UploadFile = File(...),
    session_files: List[UploadFile] = File(...)
):
    """Import accounts from CSV and session files"""
    try:
        # Read CSV content
        csv_content = (await csv_file.read()).decode('utf-8')
        
        # Read session files
        session_file_dict = {}
        for session_file in session_files:
            content = await session_file.read()
            session_file_dict[session_file.filename] = content
        
        # Import accounts
        result = await account_mgr.import_from_csv(csv_content, session_file_dict)
        
        return {
            "status": "success",
            "imported": result['imported'],
            "errors": result['errors'],
            "total": result['total']
        }
        
    except Exception as e:
        print(f"Error importing accounts: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/auth/start")
async def start_account_auth(data: dict):
    """Start account authorization - send code to Telegram"""
    try:
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        phone = data.get('phone')
        proxy = data.get('proxy')
        
        if not all([api_id, api_hash, phone]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        result = await account_mgr.start_auth(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            proxy=proxy
        )
        
        if result['status'] == 'flood_wait':
            raise HTTPException(
                status_code=429,
                detail=f"Telegram ограничил запросы. Подождите {result['wait_seconds']} секунд"
            )
        
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error starting auth: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/auth/code")
async def submit_auth_code(data: dict):
    """Submit SMS code for account authorization"""
    try:
        account_id = data.get('account_id')
        code = data.get('code')
        
        if not all([account_id, code]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        result = await account_mgr.submit_code(int(account_id), code)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error submitting code: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/auth/password")
async def submit_auth_password(data: dict):
    """Submit 2FA password for account authorization"""
    try:
        account_id = data.get('account_id')
        password = data.get('password')
        
        if not all([account_id, password]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        result = await account_mgr.submit_password(int(account_id), password)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error submitting password: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/test-proxy")
async def test_proxy_connection(data: dict):
    """Test proxy connection to Telegram"""
    try:
        proxy_config = {
            'type': data.get('type', 'socks5'),
            'host': data.get('host'),
            'port': data.get('port'),
            'username': data.get('username', ''),
            'password': data.get('password', '')
        }
        
        if not all([proxy_config['host'], proxy_config['port']]):
            raise HTTPException(status_code=400, detail="Missing proxy host or port")
        
        result = await account_mgr.test_proxy(proxy_config)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error testing proxy: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/list")
async def get_accounts_list():
    """Get list of accounts with masked sensitive data"""
    try:
        accounts = account_mgr.get_accounts_list(mask_sensitive=True)
        return {"accounts": accounts}
        
    except Exception as e:
        print(f"Error getting accounts: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    """Delete account and its session file"""
    try:
        success = await account_mgr.delete_account(account_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {"status": "success", "message": "Account deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting account: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# END ACCOUNT MANAGEMENT API
# ============================================


# ============================================================
# ИТОГО: 4 изменения в main.py
# ============================================================
# 1. Строка 6: добавить UploadFile, File в импорты
# 2. После строки 13: добавить from account_manager import AccountManager
# 3. После строки 29: добавить account_mgr = AccountManager()
# 4. Перед if __name__ == "__main__": вставить все 7 endpoints выше
#
# После этого перезапустить сервер: Ctrl+C, затем python main.py
# ============================================================
