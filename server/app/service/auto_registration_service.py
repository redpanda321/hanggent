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
Auto-Registration Service — create Hanggent accounts from IM messages.

When an unknown IM user sends a message to a shared Hanggent bot, this
service:

1. Creates a new ``User`` with a synthetic email and random password.
2. Creates a ``ChannelUserMapping`` for the IM identity.
3. Populates ``User.bot_channels`` so OpenClaw knows about the channel.
4. Starts the user's OpenClaw gateway.

The user gets immediate full AI assistant access via IM.  They can later
set real credentials through the web UI or a bot command.
"""

import asyncio
import logging
import secrets
import string
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.component.encrypt import password_hash
from app.model.user.channel_user_mapping import ChannelUserMapping
from app.model.user.user import User
from app.service import channel_mapping_service, openclaw_service

logger = logging.getLogger(__name__)

# Supported channel types
SUPPORTED_CHANNELS = frozenset({
    "telegram",
    "discord",
    "slack",
    "whatsapp",
    "line",
    "feishu",
    "signal",
    "irc",
    "matrix",
    "msteams",
    "googlechat",
    "webchat",
})


def _generate_password(length: int = 24) -> str:
    """Generate a cryptographically random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _synthetic_email(channel_type: str, channel_user_id: str) -> str:
    """Build a deterministic placeholder email for an auto-registered user.

    Format: ``{channel_user_id}@{channel_type}.im.hanggent``
    """
    # Sanitise the channel_user_id for use in an email local-part
    safe_id = "".join(c if c.isalnum() or c in "._+-" else "_" for c in str(channel_user_id))
    return f"{safe_id}@{channel_type}.im.hanggent"


def _channel_bot_config(channel_type: str, channel_user_id: str) -> dict[str, Any]:
    """Build the ``bot_channels`` entry for the auto-registered channel.

    Uses ``mode: shared`` so the gateway knows that messages are proxied
    from the server-level shared bot, not from its own connection.
    """
    base: dict[str, Any] = {"mode": "shared"}

    if channel_type == "telegram":
        # Store as int for Telegram chatId compatibility
        try:
            base["chatId"] = int(channel_user_id)
        except ValueError:
            base["chatId"] = channel_user_id
    else:
        base["channelUserId"] = channel_user_id

    return base


def auto_register_from_channel(
    channel_type: str,
    channel_user_id: str,
    *,
    channel_username: str | None = None,
    channel_metadata: dict[str, Any] | None = None,
    s: Session,
) -> tuple[User, ChannelUserMapping, bool]:
    """Look up or auto-register a Hanggent user from an IM identity.

    Returns ``(user, mapping, is_new_user)`` where ``is_new_user`` is
    ``True`` when a brand-new account was created.

    This function is **synchronous** (DB only).  The caller is expected
    to call ``ensure_bot_running_fire_and_forget`` afterwards.
    """
    if channel_type not in SUPPORTED_CHANNELS:
        raise ValueError(f"Unsupported channel type: {channel_type}")

    # ── 1. Existing mapping? ────────────────────────────────────────────
    mapping = channel_mapping_service.find_user_by_channel(
        channel_type, channel_user_id, s=s,
    )
    if mapping:
        user = s.get(User, mapping.user_id)
        if not user:
            logger.error(
                "Orphaned channel mapping — user %s not found",
                mapping.user_id,
            )
            raise RuntimeError(f"User {mapping.user_id} referenced by mapping does not exist")

        # Refresh username if it changed
        if channel_username and channel_username != mapping.channel_username:
            channel_mapping_service.update_mapping(
                mapping, channel_username=channel_username, s=s,
            )

        return user, mapping, False

    # ── 2. Create new user ──────────────────────────────────────────────
    email = _synthetic_email(channel_type, channel_user_id)
    raw_password = _generate_password()
    hashed_pw = password_hash(raw_password)

    # Build display name from whatever the channel provides
    display_name = channel_username or f"{channel_type}_{channel_user_id}"

    # Bot channels config
    bot_channels: dict[str, Any] = {
        channel_type: _channel_bot_config(channel_type, channel_user_id),
    }

    user = User(
        email=email,
        password=hashed_pw,
        nickname=display_name[:64],
        bot_channels=bot_channels,
    )
    s.add(user)
    s.commit()
    s.refresh(user)

    logger.info(
        "Auto-registered new user from IM",
        extra={
            "user_id": user.id,
            "channel": channel_type,
            "channel_user_id": channel_user_id,
            "email": email,
        },
    )

    # ── 3. Create channel mapping ───────────────────────────────────────
    mapping = channel_mapping_service.create_mapping(
        user_id=user.id,
        channel_type=channel_type,
        channel_user_id=channel_user_id,
        channel_username=channel_username,
        channel_metadata=channel_metadata,
        auto_registered=True,
        s=s,
    )

    return user, mapping, True


async def ensure_gateway_for_user(user: User) -> None:
    """Start the user's OpenClaw gateway if not already running.

    Fire-and-forget — errors are logged but not raised.
    """
    await openclaw_service.ensure_bot_running_fire_and_forget(
        user.id,
        dict(user.bot_channels or {}),
    )
