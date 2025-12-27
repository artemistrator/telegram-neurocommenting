# Fix Summary: Promo Post Publishing Issue

## Problem
The Setup Worker was skipping promo post publishing when a channel already existed because the logic was tied to channel creation.

## Root Cause
In the `create_channel_with_post` function, if a channel already existed (personal_channel_url was set), the function would return early and skip the promo post publishing entirely.

## Solution Implemented

### 1. Separated Concerns
- Split `create_channel_with_post` into two functions:
  - `create_channel_only`: Handles only channel creation
  - `publish_promo_post`: Handles only promo post publishing

### 2. Updated Import
- Added `PeerChannel` to the imports: `from telethon.tl.types import InputChatUploadedPhoto, PeerChannel`

### 3. Modified Channel Creation Logic
- Renamed function from `create_channel_with_post` to `create_channel_only`
- When channel already exists, it now attempts to get the channel entity for use in promo post publishing
- Changed log message from "SKIP channel: personal_channel_url already set" to "SKIP channel creation: already exists"

### 4. Independent Promo Post Publishing
- Created new `publish_promo_post` function that:
  - Checks if promo post already exists (idempotency)
  - Validates required data (channel_id, post_text, target_link)
  - Resolves channel entity using PeerChannel
  - Publishes the post with proper error handling
  - Updates Directus with the message ID
  - Continues setup even if promo post fails (non-blocking)

### 5. Updated Workflow
- Changed the setup workflow to call `create_channel_only` instead of `create_channel_with_post`
- Replaced the complex promo post logic with a simple call to `publish_promo_post`
- Simplified error handling and logging

## Expected Behavior
Now when an account has:
- personal_channel_url = filled
- personal_channel_id = filled  
- promo_post_message_id = null

The setup worker will:
1. Skip channel creation with message "SKIP channel creation: already exists"
2. Proceed to publish promo post with message "Step 3: Publishing promo post..."
3. Update promo_post_message_id in Directus
4. Show success message "✓ Promo post published: message_id=123"

## Files Modified
- `backend/workers/setup_worker.py`