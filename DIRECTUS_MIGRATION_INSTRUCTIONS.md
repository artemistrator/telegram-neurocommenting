# Directus Migration Instructions for Templates Collection

## Overview
This migration adds two new JSON fields to the existing `setup_templates` collection to separate profile configuration from comment policy configuration:

- `profile_config` (JSON) - Stores profile-related fields
- `comment_config` (JSON) - Stores comment policy-related fields

## Migration Steps

### Step 1: Add New Fields to setup_templates Collection

1. Navigate to Settings > Data Model > setup_templates in your Directus admin panel
2. Add the following fields:

#### Field 1: profile_config
- Interface: JSON
- Field Type: JSON
- Field Name: profile_config
- Key: profile_config
- Required: No
- Default Value: `{}` (empty JSON object)

#### Field 2: comment_config
- Interface: JSON
- Field Type: JSON
- Field Name: comment_config
- Key: comment_config
- Required: No
- Default Value: `{}` (empty JSON object)

### Step 2: Update Existing Records (Optional - for backward compatibility)

To ensure existing templates continue to work, you may want to run a script that migrates existing data to the new structure. This can be done manually or via a one-time script that:

1. Reads each template record
2. Moves profile-related fields (first_name, last_name, bio, avatar, channel_title, channel_description, post_text_template) to profile_config
3. Moves comment-related fields (commenting_prompt, style, tone, max_words, filter_mode, filter_keywords, min_post_length) to comment_config

### Field Mapping Reference

#### Profile Config Fields
The following fields should be moved to `profile_config`:
- first_name
- last_name
- bio
- avatar
- channel_title
- channel_description
- post_text_template

#### Comment Config Fields
The following fields should be moved to `comment_config`:
- commenting_prompt
- style
- tone
- max_words
- filter_mode
- filter_keywords
- min_post_length

### Notes
- The original fields can remain in place for backward compatibility
- The new structure will be used by the updated frontend/backend
- Existing integrations that rely on the old field structure will continue to work