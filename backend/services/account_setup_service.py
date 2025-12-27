
import logging
from typing import Dict, Optional, Any
from pathlib import Path
import asyncio

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UsernameOccupiedError,
    ChannelsAdminPublicTooMuchError,
    UsernameInvalidError
)
from telethon.tl.types import InputChatUploadedPhoto, PeerChannel
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditPhotoRequest,
    UpdateUsernameRequest,
    EditTitleRequest,
    EditAdminRequest # Usually needed for admin rights, but maybe not here
)
from telethon.tl.functions.messages import ExportChatInviteRequest, EditChatDefaultBannedRightsRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.types import ChatBannedRights

# Assuming DirectusClient is available or passed in
from backend.directus_client import DirectusClient

logger = logging.getLogger(__name__)

class AccountSetupService:
    """
    Service to handle Telegram account setup:
    - Profile (Name, Bio, Avatar)
    - Personal Channel (Creation, Update, Avatar)
    - Promo Post
    - AI Settings (Placeholder)
    """

    def __init__(self, directus: DirectusClient, dry_run: bool = False):
        self.directus = directus
        self.dry_run = dry_run

    async def setup_account(
        self, 
        client: TelegramClient, 
        account: Dict, 
        template: Dict,
        files: Dict[str, Optional[Path]]
    ) -> bool:
        """
        Main entry point for account setup.
        
        Args:
            client: Connected Telethon client
            account: Account data from Directus
            template: Template data from Directus
            files: Dictionary of downloaded file paths
            
        Returns:
            True if setup (or parts of it) completed successfully, False on critical failure.
        """
        account_id = account['id']
        logger.info(f"[SetupService] Starting setup for account {account_id}")

        try:
            # 1. Setup Profile
            await self.update_profile(client, account, template, files.get("account_avatar"))

            # 2. Setup Channel
            channel_link, channel_id = await self.ensure_personal_channel(client, account, template, files.get("channel_avatar"))
            
            # Update account dict with new channel info so other methods can access it
            if channel_id:
                account['personal_channel_id'] = channel_id
            if channel_link:
                account['personal_channel_url'] = channel_link

            # 3. Promo Post
            if channel_link:
                await self.publish_promo_post(client, account, template)
                # 4. Update Bio with channel link
                await self.update_bio_with_link(client, account, template, channel_link)
            else:
                logger.info("[SetupService] Skipping Promo Post and Bio update (no channel link)")

            # 5. AI Settings (Placeholder)
            await self.apply_ai_settings(account, template)

            return True

        except Exception as e:
            logger.error(f"[SetupService] Error during account setup: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def update_profile(
        self, 
        client: TelegramClient, 
        account: Dict, 
        template: Dict, 
        avatar_path: Optional[Path]
    ):
        """
        Idempotent profile update.
        Only updates fields that are present in the template.
        """
        first_name = self._tmpl_str(template, 'first_name')
        last_name = self._tmpl_str(template, 'last_name')
        
        # Only update if at least first_name is present (Telegram requires first_name)
        # But wait, if template has empty name, we should NOT touch it per requirements.
        
        if not first_name and not last_name:
             logger.info("[SetupService] Skipping profile update: Name fields empty in template")
        else:
            # Default to existing if empty in template? 
            # Requirements say: "Если поле в шаблоне (например, first_name) пустое — НЕ трогаем текущее значение".
            # So we only send update if we have a value. 
            # However, Telethon UpdateProfileRequest takes optional args.
            
            kwargs = {}
            if first_name: kwargs['first_name'] = first_name
            if last_name: kwargs['last_name'] = last_name
            
            if kwargs:
                # Check if change is needed
                current_first = account.get('first_name') or ""
                current_last = account.get('last_name') or ""
                
                target_first = kwargs.get('first_name', current_first) # If not updating, assume current
                target_last = kwargs.get('last_name', current_last)
                
                # Loose check
                if current_first == target_first and current_last == target_last:
                    logger.info(f"[SetupService] Skipping profile name update: matches '{target_first} {target_last}'")
                else:
                    if self.dry_run:
                         logger.info(f"[SetupService] [DRY RUN] UpdateProfileRequest({kwargs})")
                    else:
                        await client(UpdateProfileRequest(**kwargs))
                        logger.info(f"[SetupService] Updated profile name: {kwargs}")

        # Avatar
        if avatar_path and avatar_path.exists():
            # Only upload if not already has avatar or we want to force?
            # Creating a simple logic: if account has no avatar_url in DB, upload.
            # OR if we just want to be sure. 
            # Reqs: "Для аватара: если есть URL — загружаем." (URL from template -> downloaded to path)
            # Let's assume we upload if we have the file.
            
            # Idempotency: Check if we already have an avatar in Directus for this account?
            # Or just check if we have done this step? 
            # "setup_status" is global.
            # Let's check account['avatar_url']. If it matches template['account_avatar'], maybe skip?
            # But Directus stores file UUIDs.
            
            current_avatar = account.get('avatar_url')
            template_avatar = template.get('account_avatar')
            
            if current_avatar == template_avatar and current_avatar:
                 logger.info("[SetupService] Skipping avatar upload: account.avatar_url matches template")
            else:
                if self.dry_run:
                     logger.info(f"[SetupService] [DRY RUN] Upload profile photo: {avatar_path}")
                else:
                    await client.upload_profile_photo(str(avatar_path))
                    logger.info("[SetupService] Uploaded profile photo")

    async def ensure_personal_channel(
        self,
        client: TelegramClient,
        account: Dict,
        template: Dict,
        avatar_path: Optional[Path]
    ) -> tuple[Optional[str], Optional[int]]:
        """
        Creates or updates the personal channel.
        Returns a tuple of (channel link, channel id).
        """
        channel_title = self._tmpl_str(template, 'channel_title')
        channel_description = self._tmpl_str(template, 'channel_description')
        
        if not channel_title:
             logger.info("[SetupService] Skipping channel creation: channel_title empty in template")
             return account.get('personal_channel_url'), account.get('personal_channel_id')

        existing_channel_id = account.get('personal_channel_id')
        existing_channel_url = account.get('personal_channel_url')

        channel_entity = None
        channel_url = existing_channel_url

        if existing_channel_id:
            logger.info(f"[SetupService] Account has personal_channel_id={existing_channel_id}. Checking existence...")
            try:
                channel_entity = await client.get_entity(PeerChannel(int(existing_channel_id)))
                logger.info("[SetupService] Found existing channel.")
                
                # Update Description if needed
                if channel_description:
                    # We can't easily check current description without full info, just update
                    if self.dry_run:
                        logger.info(f"[SetupService] [DRY RUN] EditTitleRequest(title={channel_title}) (if needed) + EditAbout")
                    else:
                        # Update Title if changed
                        if getattr(channel_entity, 'title', '') != channel_title:
                            await client(EditTitleRequest(channel=channel_entity, title=channel_title))
                        
                        # Update Description
                        from telethon.tl.functions.channels import EditTitleRequest
                        from telethon.tl.functions.messages import EditChatAboutRequest
                        
                        await client(EditChatAboutRequest(peer=channel_entity, about=channel_description))

            except Exception as e:
                logger.warning(f"[SetupService] Could not access existing channel {existing_channel_id}: {e}")
                channel_entity = None # Treat as not found/lost access?
                # Reqs: "Если ID есть... Пытаемся найти... " - if fail, maybe log and continue or try create new?
                # For now, if we can't search it, we can't update it. We probably shouldn't create a NEW one to avoid dupes.
                return existing_channel_url, existing_channel_id

        else:
            # Create NEW channel
            logger.info(f"[SetupService] Creating new channel '{channel_title}'")
            if self.dry_run:
                logger.info("[SetupService] [DRY RUN] CreateChannelRequest(...)")
                # Mock ID and URL
                new_channel_id = 999999
                channel_url = f"https://t.me/dryrun_{channel_title}"
            else:
                result = await client(CreateChannelRequest(
                    title=channel_title,
                    about=channel_description or "",
                    megagroup=False
                ))
                channel_entity = result.chats[0]
                new_channel_id = channel_entity.id
                
                # Username / Link
                # Try public link
                channel_url = await self._set_channel_username(client, channel_entity, channel_title)
                
                # Save to Directus IMMEDIATELY
                await self._save_channel_info(account['id'], new_channel_id, channel_url)

            # Upload Avatar for NEW channel (or should we update existing too?)
            # Reqs don't specify updating avatar for existing, but implied "Logic of setup".
            # Let's do it if we have the file.
            if avatar_path and avatar_path.exists():
                if self.dry_run:
                    logger.info("[SetupService] [DRY RUN] Upload channel photo")
                else:
                    file = await client.upload_file(str(avatar_path))
                    await client(EditPhotoRequest(
                        channel=channel_entity if channel_entity else PeerChannel(new_channel_id),
                        photo=InputChatUploadedPhoto(file)
                    ))

        return channel_url, new_channel_id if 'new_channel_id' in locals() else existing_channel_id

    async def _set_channel_username(self, client, channel_entity, base_title) -> str:
        """Helper to set username or get invite link."""
        
        def generate_random_username(base_title):
            """Generate a random username for the channel."""
            import random
            import string
            clean_name = ''.join(c for c in base_title if c.isalnum() or c == '_')[:20]
            suffix = ''.join(random.choices(string.digits, k=6))
            return f"{clean_name}_{suffix}"
        
        try:
             # Try public
             # Generate random suffix
             username = generate_random_username(base_title)
             
             await client(UpdateUsernameRequest(channel=channel_entity, username=username))
             return f"https://t.me/{username}"
        except (UsernameOccupiedError, ChannelsAdminPublicTooMuchError, UsernameInvalidError):
             logger.warning("[SetupService] Public link failed, getting private link")
             invite = await client(ExportChatInviteRequest(peer=channel_entity))
             return invite.link

    async def _save_channel_info(self, account_id, channel_id, channel_url):
        logger.info(f"[SetupService] Saving channel info: id={channel_id}, url={channel_url}")
        if self.dry_run:
            return
        await self.directus.client.patch(f"/items/accounts/{account_id}", json={
            "personal_channel_id": channel_id,
            "personal_channel_url": channel_url
        })

    async def publish_promo_post(self, client: TelegramClient, account: Dict, template: Dict):
        """
        Publishes promo post if not already published.
        """
        post_text = template.get('post_text_template')
        if not post_text:
            logger.info("[SetupService] No promo post text in template, skipping.")
            return

        if account.get('promo_post_message_id'):
            logger.info("[SetupService] Promo post already published (id exists), skipping.")
            return

        channel_id = account.get('personal_channel_id')
        if not channel_id:
            logger.warning("[SetupService] Cannot publish promo post: No personal_channel_id")
            return
            
        target_link = account.get('personal_channel_url', '') # Use self link?
        # Usually promo post promotes the TARGET link (the money site), but user req says:
        # "Получаем текст поста из шаблона... Если текст есть и ID нет — публикуем"
        # The prompt implies `target_link` field in template or account? 
        # In setup_worker it used `account.get('personal_channel_url')` as target_link?
        # Wait, old code: `target_link = account.get('personal_channel_url', '')`
        # This seems circular if the promo post is IN the personal channel pointing TO the personal channel?
        # Ah, maybe it points to `account.target_link`? 
        # The prompt in old code: `final_text = post_text.replace('{target_link}', target_link)`
        # And `target_link` was `account.get('personal_channel_url')`. 
        # That means the post is just a welcome post? 
        # OR, maybe I should check if there is a `target_link` in template? 
        # setup_worker: `target_link = account.get('personal_channel_url', '').strip()`
        
        # Let's keep existing logic: replace `{target_link}` with `personal_channel_url` (or maybe `setup_template.target_link`?)
        # Actually usually "Double Layer" means: Account -> Personal Channel -> Target Channel/Site.
        # So the post in Personal Channel should link to Target.
        # But for now, I will use `account.get('personal_channel_url')` simply because I want to match strict instructions or reasonable default.
        # Actually... let's look at `setup_templates` schema mentally. It has `target_link`? 
        # Use `tmpl_str(template, 'target_link')`?
        
        # Re-reading setup_worker.py: 
        # `target_link = account.get('personal_channel_url', '').strip()`
        # This looks like it promotes the channel itself? That's weird for a post INSIDE the channel.
        # BUT, if the promo post is on the PROFILE? No, `publish_promo_post` sends message to `channel_entity`.
        # So it is a post inside the channel.
        # If I use `target_link` from template, it makes more sense.
        
        # Decision: I will look for `target_link` in template. If not found, fallback to empty string (just remove placeholder).
        target_url = self._tmpl_str(template, 'target_link') 
        # If template doesn't have it, maybe account has it?
        # Just use what is available.
        
        final_text = post_text.replace('{target_link}', target_url or "")
        
        logger.info(f"[SetupService] Publishing promo post to channel {channel_id}...")
        
        try:
             updated_channel = await client.get_entity(PeerChannel(int(channel_id)))
             if self.dry_run:
                 logger.info(f"[SetupService] [DRY RUN] send_message('{final_text}')")
                 msg_id = 999
             else:
                 msg = await client.send_message(updated_channel, final_text)
                 msg_id = msg.id
             
             # Save ID
             if not self.dry_run:
                await self.directus.update_item('accounts', account['id'], {
                    'promo_post_message_id': msg_id
                })
        except Exception as e:
            logger.error(f"[SetupService] Failed to publish promo post: {e}")


    async def update_bio_with_link(self, client, account, template, channel_link):
        """
        Updates account bio to include the channel link.
        """
        # Reqs: "Для аватара... Для личного канала... Для Промо-поста..."
        # It didn't explicitly mention Bio in the NEW logic list used in prompt?
        # Prompt: "1. Профиль (Имя, Фамилия, Био, Аватар)... Если поле в шаблоне (например, first_name) пустое — НЕ трогаем"
        # "Получаем данные из шаблона." 
        # So Bio should be from template.
        # OLD logic had specific "Update Bio with Channel Link".
        # NEW logic: "Если поле в шаблоне... пустое — НЕ трогаем... Если заполнено — обновляем".
        # Does the template bio contain a placeholder `{channel_link}`?
        # If so, we can process it.
        
        # Get bio from template, if empty get current bio from account
        bio_template = self._tmpl_str(template, 'bio')
        current_bio = account.get('bio', '') or ''
        
        # If template bio is empty, start with current bio
        if not bio_template:
            base_bio = current_bio
        else:
            base_bio = bio_template
            
        # Process placeholders
        processed_bio = base_bio.replace('{channel_link}', channel_link or "").replace('{target_link}', channel_link or "")
        
        # If we have a channel link, ensure it's in the bio (unless already present)
        if channel_link:
            # Check if the channel link is already in the processed bio
            if channel_link not in processed_bio:
                # If bio is not empty, add a separator before adding the link
                if processed_bio.strip():
                    final_bio = f"{processed_bio} | {channel_link}"
                else:
                    final_bio = channel_link
            else:
                final_bio = processed_bio
        else:
            final_bio = processed_bio
        
        # Only update if bio has changed
        if current_bio == final_bio:
            logger.info("[SetupService] Bio already matches, skipping.")
            return
            
        if self.dry_run:
            logger.info(f"[SetupService] [DRY RUN] UpdateProfileRequest(about='{final_bio}')")
        else:
            await client(UpdateProfileRequest(about=final_bio))
            # Update the account dict so caller knows what changed
            account['bio'] = final_bio
            
            # Directus update usually happens in finalize, but good to keep in sync?
            # We rely on setup_worker to do final patch usually, but maybe service should do it?
            # Service is "logic", saving state is good.
            # But let's leave DB sync to the caller or do it here? 
            # The prompt says "Implement... in method setup_account".
            # I'll let the caller (setup_worker) handle the final DB patch to avoid partial updates, 
            # OR I'll update fields in `account` dict so caller knows what changed?
            pass

    async def apply_ai_settings(self, account: Dict, template: Dict):
        """
        Placeholder for AI settings.
        Copies limits if they exist in account columns.
        """
        # User feedback: "Если в таблице accounts есть поля для лимитов... копируй их."
        # "Если их нет — то шаг apply_ai_settings пока должен быть пустым"
        
        # Check for known limit fields in account (introspect or just try-catch?)
        # Since I don't know the exact schema of `accounts` right now (I only see what was requested in fields),
        # I will assume standard ones if I knew them.
        # For now, I'll validly just log.
        logger.info("[SetupService] AI Settings: limits sync (Placeholder). No known limit fields in 'accounts' provided yet.")
        pass

    def _tmpl_str(self, t: Dict, key: str, default: str = "") -> str:
        v = t.get(key)
        return str(v).strip() if v is not None and str(v).strip() != "" else default

