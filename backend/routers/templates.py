"""
Templates API Router
Handles CRUD operations for setup templates
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging

from backend.directus_client import directus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    # Profile config fields (kept for backward compatibility)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None  # file ID or URL
    channel_title: Optional[str] = None
    channel_description: Optional[str] = None
    post_text_template: Optional[str] = None
    # Comment config fields (kept for backward compatibility)
    commenting_prompt: Optional[str] = None
    style: Optional[str] = None
    tone: Optional[str] = None
    max_words: Optional[int] = None
    filter_mode: Optional[str] = None
    filter_keywords: Optional[str] = None
    min_post_length: Optional[int] = None
    # New structured fields
    profile_config: Optional[dict] = None
    comment_config: Optional[dict] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    # Profile config fields (kept for backward compatibility)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    channel_title: Optional[str] = None
    channel_description: Optional[str] = None
    post_text_template: Optional[str] = None
    # Comment config fields (kept for backward compatibility)
    commenting_prompt: Optional[str] = None
    style: Optional[str] = None
    tone: Optional[str] = None
    max_words: Optional[int] = None
    filter_mode: Optional[str] = None
    filter_keywords: Optional[str] = None
    min_post_length: Optional[int] = None
    # New structured fields
    profile_config: Optional[dict] = None
    comment_config: Optional[dict] = None


@router.get("/list")
async def list_templates():
    """
    Get list of all setup templates.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
            
        # Get templates
        response = await directus.client.get("/items/setup_templates", params={
            "fields": "*",
            "sort": "-date_created"
        })
        
        response.raise_for_status()
        data = response.json()
        
        templates = data.get('data', [])
        
        return {
            'templates': templates,
            'total': len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_template(template_in: TemplateCreate):
    """
    Create a new setup template.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
            
        # Validate required field
        if not template_in.name:
            raise HTTPException(status_code=400, detail="Name is required")
            
        # Prepare template data with both old and new structures
        template_data = {
            "name": template_in.name,
            # Keep old fields for backward compatibility
            "first_name": template_in.first_name,
            "last_name": template_in.last_name,
            "bio": template_in.bio,
            "avatar": template_in.avatar,
            "channel_title": template_in.channel_title,
            "channel_description": template_in.channel_description,
            "post_text_template": template_in.post_text_template,
            "commenting_prompt": template_in.commenting_prompt,
            "style": template_in.style,
            "tone": template_in.tone,
            "max_words": template_in.max_words,
            "filter_mode": template_in.filter_mode,
            "filter_keywords": template_in.filter_keywords,
            "min_post_length": template_in.min_post_length,
            # Add new structured fields
            "profile_config": template_in.profile_config or {},
            "comment_config": template_in.comment_config or {}
        }
        
        template = await directus.create_item("setup_templates", template_data)
        
        logger.info(f"✓ Created template {template_in.name}")
        
        return {
            "status": "success",
            "template": template
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{template_id}")
async def update_template(template_id: int, template_update: TemplateUpdate):
    """
    Update template fields.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
            
        # Prepare update data (only include fields that are not None)
        update_data = {}
        if template_update.name is not None:
            update_data["name"] = template_update.name
        # Keep old fields for backward compatibility
        if template_update.first_name is not None:
            update_data["first_name"] = template_update.first_name
        if template_update.last_name is not None:
            update_data["last_name"] = template_update.last_name
        if template_update.bio is not None:
            update_data["bio"] = template_update.bio
        if template_update.avatar is not None:
            update_data["avatar"] = template_update.avatar
        if template_update.channel_title is not None:
            update_data["channel_title"] = template_update.channel_title
        if template_update.channel_description is not None:
            update_data["channel_description"] = template_update.channel_description
        if template_update.post_text_template is not None:
            update_data["post_text_template"] = template_update.post_text_template
        if template_update.commenting_prompt is not None:
            update_data["commenting_prompt"] = template_update.commenting_prompt
        if template_update.style is not None:
            update_data["style"] = template_update.style
        if template_update.tone is not None:
            update_data["tone"] = template_update.tone
        if template_update.max_words is not None:
            update_data["max_words"] = template_update.max_words
        if template_update.filter_mode is not None:
            update_data["filter_mode"] = template_update.filter_mode
        if template_update.filter_keywords is not None:
            update_data["filter_keywords"] = template_update.filter_keywords
        if template_update.min_post_length is not None:
            update_data["min_post_length"] = template_update.min_post_length
        # Add new structured fields if provided
        if template_update.profile_config is not None:
            update_data["profile_config"] = template_update.profile_config
        if template_update.comment_config is not None:
            update_data["comment_config"] = template_update.comment_config
            
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
            
        # Update template in Directus
        updated_template = await directus.update_item("setup_templates", template_id, update_data)
        
        logger.info(f"✓ Updated template {template_id} with {update_data}")
        
        return {
            "status": "success",
            "template": updated_template
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}")
async def delete_template(template_id: int):
    """
    Delete template.
    """
    try:
        # Ensure Directus is logged in
        if not directus.token:
            await directus.login()
        
        # Delete template
        delete_response = await directus.client.delete(f"/items/setup_templates/{template_id}")
        delete_response.raise_for_status()
        
        logger.info(f"✓ Template {template_id} deleted")
        
        return {
            'status': 'success',
            'message': f'Template {template_id} deleted'
        }
        
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))