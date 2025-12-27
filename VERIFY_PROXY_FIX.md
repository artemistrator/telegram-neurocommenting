# Directus Fields Query Encoding Fix Verification

## Problem Summary
Workers were experiencing 403 Forbidden errors after container restarts due to field name corruption in Directus requests. Specifically, `proxy_id.*` was being transformed to `proxyid.2A` (missing underscore and improper encoding), causing Directus to reject the requests.

## Solution Implemented
1. Added `build_safe_params()` helper in `directus_client.py` to properly handle field parameters
2. Added `safe_get()` wrapper with debug logging for non-200 responses
3. Updated all workers to use `directus.safe_get()` instead of `directus.client.get()`

## How to Verify the Fix

### 1. Restart Containers
```bash
docker compose down
docker compose up -d
```

### 2. Monitor Worker Logs
Watch the logs for the workers to ensure they're functioning correctly without 403 errors:

```bash
# Watch setup-worker logs
docker compose logs -f setup-worker

# Watch listener logs  
docker compose logs -f listener

# Watch health-checker logs
docker compose logs -f health-checker

# Watch other workers
docker compose logs -f subscription-worker
docker compose logs -f commenting-worker
docker compose logs -f parser-worker
```

### 3. Success Indicators
Look for these log entries that confirm the fix is working:

#### Setup Worker
- `[Setup] ✓ Подключение к Directus установлено` - Connection successful
- `[Setup] Found 1 pending accounts` - Account query working (should include proxy fields)
- No 403 errors in logs

#### Listener Worker
- `[Listener] ✓ Directus connection OK` - Connection successful
- `[Listener] Polling for active channels...` - Channel query working
- No 403 errors in logs

#### Health Checker
- `[Health] ✓ Directus connection OK` - Connection successful
- `[Health] Checking 1 accounts` - Account query working (should include proxy fields)
- No 403 errors in logs

#### Other Workers
- Similar success messages indicating queries are working
- No 403 Forbidden errors

### 4. Debugging 403 Issues
If you still see 403 errors, look for debug logs like:
```
[DEBUG] Directus request failed with status 403
[DEBUG] URL: http://directus:8055/items/accounts?...
[DEBUG] Params: {...}
```

These logs will show the exact request that's failing, helping diagnose any remaining issues.

## Field Usage Standardization
All workers now use standardized field lists:
- For proxy relation: `proxy_id.*` (wildcard) or explicit list:
  `proxy_id.id,proxy_id.host,proxy_id.port,proxy_id.type,proxy_id.username,proxy_id.password,proxy_id.status,proxy_id.assigned_to`
- For personal channels: `personal_channel_id`
- All fields preserve underscores exactly as intended

## Files Updated
1. `backend/directus_client.py` - Added safe parameter handling
2. `backend/workers/setup_worker.py` - Updated to use safe_get
3. `backend/workers/listener_worker.py` - Updated to use safe_get
4. `backend/workers/account_health_checker.py` - Updated to use safe_get
5. `backend/workers/parser_worker.py` - Updated to use safe_get
6. `backend/workers/commenting_worker.py` - Updated to use safe_get
7. `backend/workers/subscription_worker.py` - Updated to use safe_get
8. `backend/workers/search_parser_worker.py` - Updated to use safe_get

This fix ensures that field names with underscores and wildcards are preserved correctly in Directus API requests, preventing the 403 Forbidden errors that were occurring after container restarts.