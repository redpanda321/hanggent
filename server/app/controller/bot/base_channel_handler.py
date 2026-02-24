# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

"""
Base Channel Webhook Handler — shared logic for all IM webhook controllers.

Each channel-specific controller subclasses ``BaseChannelHandler`` and
implements the platform-specific extraction / reply methods.  The base
class provides:

* Auto-registration flow (first message creates account + mapping)
* Rate limiting checks
* Message routing to the user's OpenClaw gateway
* Welcome message delivery for new users
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from app.component.database import session_make
from app.component import im_channel_config
from app.service import auto_registration_service, channel_mapping_service, openclaw_service

logger = logging.getLogger(__name__)

# Simple in-memory rate limiters (per-channel, per-user-id)
_registration_timestamps: dict[str, list[float]] = defaultdict(list)
_message_timestamps: dict[str, list[float]] = defaultdict(list)


def _rate_check(
    bucket: dict[str, list[float]],
    key: str,
    max_count: int,
    window_seconds: float,
) -> bool:
    """Return ``True`` if within rate limit, ``False`` if exceeded."""
    now = time.monotonic()
    times = bucket[key]
    # Prune old entries
    bucket[key] = [t for t in times if now - t < window_seconds]
    if len(bucket[key]) >= max_count:
        return False
    bucket[key].append(now)
    return True


class BaseChannelHandler:
    """Abstract base for IM webhook controllers.

    Subclasses MUST override:
    * ``channel_type``       — e.g. ``"telegram"``, ``"discord"``
    * ``extract_user_id()``  — platform-specific sender ID
    * ``extract_username()`` — platform-specific @handle
    * ``send_reply()``       — platform-specific reply method
    * ``extract_metadata()`` — optional extra context

    Then call ``handle_message()`` from the webhook endpoint.
    """

    channel_type: str = ""

    # ── To be overridden ────────────────────────────────────────────────

    def extract_user_id(self, payload: dict) -> str | None:
        """Extract the sender's platform-specific user/chat ID."""
        raise NotImplementedError

    def extract_username(self, payload: dict) -> str | None:
        """Extract the sender's human-readable handle (optional)."""
        return None

    def extract_text(self, payload: dict) -> str:
        """Extract the message text (empty string if media-only)."""
        return ""

    def extract_metadata(self, payload: dict) -> dict[str, Any] | None:
        """Extract optional extra metadata (display name, avatar, etc.)."""
        return None

    async def send_reply(self, channel_user_id: str, text: str) -> None:
        """Send a text reply back to the IM user."""
        raise NotImplementedError

    # ── Shared logic ────────────────────────────────────────────────────

    async def handle_message(self, payload: dict) -> dict:
        """Main entry point — called by the webhook endpoint.

        1. Extract sender identity
        2. Rate check
        3. Check for /link command (account linking)
        4. Auto-register if needed
        5. Route to OpenClaw gateway
        6. Send welcome message for new users
        """
        channel_user_id = self.extract_user_id(payload)
        if not channel_user_id:
            return {"ok": True, "skipped": "no_user_id"}

        username = self.extract_username(payload)
        metadata = self.extract_metadata(payload)
        text = self.extract_text(payload)

        # Rate limit messages
        settings = im_channel_config.get_settings()
        msg_limit = settings.get("rate_limit_messages_per_minute", 30)
        msg_key = f"{self.channel_type}:{channel_user_id}"
        if not _rate_check(_message_timestamps, msg_key, msg_limit, 60):
            logger.warning("Rate limit exceeded for %s", msg_key)
            return {"ok": True, "skipped": "rate_limited"}

        # Handle /link command — link IM identity to existing web account
        if text.strip().startswith("/link "):
            return await self._handle_link_command(
                str(channel_user_id), text.strip(), username, metadata,
            )

        # Look up or auto-register
        s = session_make()
        try:
            user, mapping, is_new = auto_registration_service.auto_register_from_channel(
                channel_type=self.channel_type,
                channel_user_id=str(channel_user_id),
                channel_username=username,
                channel_metadata=metadata,
                s=s,
            )
            user_id = user.id
            bot_channels = dict(user.bot_channels or {})
        except Exception:
            logger.exception("Auto-registration failed for %s:%s", self.channel_type, channel_user_id)
            return {"ok": False, "error": "registration_failed"}
        finally:
            s.close()

        # Rate limit registrations (only counts when is_new)
        if is_new:
            reg_limit = settings.get("rate_limit_registrations_per_hour", 60)
            reg_key = f"reg:{self.channel_type}"
            if not _rate_check(_registration_timestamps, reg_key, reg_limit, 3600):
                logger.warning("Registration rate limit exceeded for %s", self.channel_type)
                # Still allow the message — the user was created already

            # Send welcome message
            welcome = im_channel_config.get_welcome_message()
            asyncio.create_task(self._safe_send_reply(str(channel_user_id), welcome))

        # Ensure gateway is running and route the message
        asyncio.create_task(self._route_to_gateway(user_id, bot_channels, payload))

        return {"ok": True, "user_id": user_id, "is_new": is_new}

    async def _handle_link_command(
        self,
        channel_user_id: str,
        text: str,
        username: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict:
        """Process ``/link <CODE>`` — link this IM identity to a web account.

        Validates the code from ``ChannelLinkingCode`` and creates/updates
        the ``ChannelUserMapping``.  If the IM user was previously
        auto-registered, re-points the mapping to the code's owner.
        """
        from datetime import datetime, timezone
        from sqlmodel import select
        from app.model.user.channel_user_mapping import ChannelLinkingCode

        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._safe_send_reply(channel_user_id, "Usage: /link <CODE>")
            return {"ok": True, "handled": "link_usage"}

        code_str = parts[1].strip()
        s = session_make()
        try:
            now = datetime.now(timezone.utc)
            link_code = s.exec(
                select(ChannelLinkingCode)
                .where(ChannelLinkingCode.code == code_str)
                .where(ChannelLinkingCode.channel_type == self.channel_type)
                .where(ChannelLinkingCode.used == False)
            ).first()

            if not link_code:
                await self._safe_send_reply(channel_user_id, "Invalid or expired code. Please try again.")
                return {"ok": True, "handled": "link_invalid"}

            if link_code.expires_at.replace(tzinfo=timezone.utc) < now:
                link_code.used = True
                s.add(link_code)
                s.commit()
                await self._safe_send_reply(channel_user_id, "This code has expired. Please generate a new one.")
                return {"ok": True, "handled": "link_expired"}

            target_user_id = link_code.user_id

            # Mark code as used
            link_code.used = True
            s.add(link_code)

            # Check if IM identity already has a mapping
            existing = channel_mapping_service.find_user_by_channel(
                self.channel_type, channel_user_id, s=s,
            )

            if existing:
                if existing.user_id == target_user_id:
                    s.commit()
                    await self._safe_send_reply(channel_user_id, "Already linked to your account!")
                    return {"ok": True, "handled": "link_already"}

                # Re-point mapping to new user
                existing.user_id = target_user_id
                existing.auto_registered = False
                existing.channel_username = username
                if metadata:
                    existing.channel_metadata = metadata
                s.add(existing)
            else:
                # Create new mapping
                channel_mapping_service.create_mapping(
                    user_id=target_user_id,
                    channel_type=self.channel_type,
                    channel_user_id=channel_user_id,
                    channel_username=username,
                    channel_metadata=metadata,
                    auto_registered=False,
                    s=s,
                )

            # Update target user's bot_channels
            from app.model.user.user import User
            target_user = s.get(User, target_user_id)
            if target_user:
                channels = dict(target_user.bot_channels or {})
                channels[self.channel_type] = channels.get(self.channel_type, {"mode": "shared"})
                target_user.bot_channels = channels
                s.add(target_user)

            s.commit()

            await self._safe_send_reply(
                channel_user_id,
                "Account linked successfully! Your messages will now be handled by your Hanggent account.",
            )

            # Ensure gateway is running for the linked user
            if target_user:
                asyncio.create_task(
                    auto_registration_service.ensure_gateway_for_user(target_user)
                )

            return {"ok": True, "handled": "link_success", "user_id": target_user_id}

        except Exception:
            logger.exception("Failed to handle /link for %s:%s", self.channel_type, channel_user_id)
            await self._safe_send_reply(channel_user_id, "An error occurred. Please try again later.")
            return {"ok": False, "error": "link_failed"}
        finally:
            s.close()

    async def _route_to_gateway(
        self,
        user_id: int,
        bot_channels: dict[str, Any],
        payload: dict,
    ) -> None:
        """Ensure gateway is running and forward the webhook payload."""
        try:
            await openclaw_service.ensure_bot_running(user_id, bot_channels)
            await openclaw_service.proxy_to_bot(
                user_id,
                f"webhook/{self.channel_type}",
                method="POST",
                body=payload,
            )
        except Exception:
            logger.exception(
                "Failed to route %s message to user %s gateway",
                self.channel_type,
                user_id,
            )

    async def _safe_send_reply(self, channel_user_id: str, text: str) -> None:
        """Send a reply, swallowing errors."""
        try:
            await self.send_reply(channel_user_id, text)
        except Exception:
            logger.exception(
                "Failed to send %s reply to %s",
                self.channel_type,
                channel_user_id,
            )
