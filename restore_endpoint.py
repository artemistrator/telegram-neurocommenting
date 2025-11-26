# Script to restore get_accounts_list endpoint
import os

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check if it's really missing
if 'def get_accounts_list' not in content:
    print("Restoring get_accounts_list endpoint...")
    
    endpoint_code = '''
@app.get("/api/accounts/list")
async def get_accounts_list():
    """Get list of accounts with masked sensitive data"""
    try:
        accounts = await account_mgr.get_accounts_list(mask_sensitive=True)
        return {"accounts": accounts}
        
    except Exception as e:
        print(f"Error getting accounts: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
'''
    
    # Insert before delete_account
    if '@app.delete("/api/accounts/{account_id}")' in content:
        content = content.replace(
            '@app.delete("/api/accounts/{account_id}")',
            f'{endpoint_code}\n\n@app.delete("/api/accounts/{{account_id}}")'
        )
        
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("✓ Endpoint restored successfully")
    else:
        print("❌ Could not find insertion point (delete_account endpoint)")
else:
    print("ℹ️ Endpoint already exists")
