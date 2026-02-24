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
Discord Webhook Controller — handles incoming interactions from the shared
Hanggent Discord bot.

Discord does NOT support traditional HTTP webhooks for *incoming* DMs.
Instead, this controller handles **Discord Interactions** (slash commands
and message components) via the Interactions Endpoint URL, which Discord
POSTs to when users invoke slash commands or interact with buttons.

For real-time DM monitoring, a persistent gateway (discord.py) is needed.
This controller provides a minimal interaction handler that can:
  * Verify Discord signatures
  * Respond to ``PING`` (endpoint verification)
  * Route DM interactions to the user's OpenClaw gateway

Routes:
  POST /webhook/discord — Discord Interactions Endpoint
"""

import hashlib
import hmac
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.component import im_channel_config
from app.controller.bot.base_channel_handler import BaseChannelHandler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Discord Webhook"])

DISCORD_PUBLIC_KEY = os.getenv("HANGGENT_DISCORD_PUBLIC_KEY", "")
DISCORD_BOT_TOKEN = os.getenv("HANGGENT_DISCORD_BOT_TOKEN", "")


def _verify_discord_signature(body: bytes, signature: str, timestamp: str) -> bool:
    """Verify the Ed25519 signature from Discord."""
    if not DISCORD_PUBLIC_KEY:
        return True  # Skip verification if no public key configured
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except ImportError:
        logger.warning("PyNaCl not installed — skipping Discord signature verification")
        return True
    except Exception:
        return False


class DiscordHandler(BaseChannelHandler):
    """Discord-specific implementation of the base channel handler."""

    channel_type = "discord"

    def extract_user_id(self, payload: dict) -> str | None:
        """Extract the Discord user ID from an interaction payload."""
        # Interaction payloads have user info at .member.user or .user
        member = payload.get("member") or {}
        user = member.get("user") or payload.get("user") or {}
        return user.get("id")

    def extract_username(self, payload: dict) -> str | None:
        member = payload.get("member") or {}
        user = member.get("user") or payload.get("user") or {}
        username = user.get("username")
        discriminator = user.get("discriminator", "0")
        if username and discriminator != "0":
            return f"{username}#{discriminator}"
        return username

    def extract_text(self, payload: dict) -> str:
        # Slash command: extract the command name + options
        data = payload.get("data") or {}
        return data.get("name", "")

    def extract_metadata(self, payload: dict) -> dict[str, Any] | None:
        member = payload.get("member") or {}
        user = member.get("user") or payload.get("user") or {}
        meta: dict[str, Any] = {}
        if user.get("global_name"):
            meta["global_name"] = user["global_name"]
        if user.get("avatar"):
            meta["avatar"] = user["avatar"]
        return meta or None

    async def send_reply(self, channel_user_id: str, text: str) -> None:
        """Send a DM to a Discord user via the Bot API."""
        if not DISCORD_BOT_TOKEN:
            return
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Create DM channel
                resp = await client.post(
                    "https://discord.com/api/v10/users/@me/channels",
                    headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                    json={"recipient_id": channel_user_id},
                )
                if resp.status_code == 200:
                    dm_channel_id = resp.json()["id"]
                    await client.post(
                        f"https://discord.com/api/v10/channels/{dm_channel_id}/messages",
                        headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                        json={"content": text},
                    )
        except Exception as e:
            logger.warning("Failed to send Discord DM to %s: %s", channel_user_id, e)


_discord_handler = DiscordHandler()


@router.post("/webhook/discord", name="discord webhook")
async def discord_webhook(request: Request):
    """Receive Discord interaction events.

    Discord POSTs interactions to this URL.  We must respond to ``PING``
    with ``PONG`` (type 1) for endpoint verification.
    """
    if not im_channel_config.is_channel_enabled("discord"):
        raise HTTPException(404, detail="Discord channel not enabled")

    body = await request.body()
    signature = request.headers.get("x-signature-ed25519", "")
    timestamp = request.headers.get("x-signature-timestamp", "")

    if not _verify_discord_signature(body, signature, timestamp):
        raise HTTPException(401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")

    # Discord PING (endpoint verification)
    if payload.get("type") == 1:
        return {"type": 1}  # PONG

    # Interaction types: 2=APPLICATION_COMMAND, 3=MESSAGE_COMPONENT, 5=MODAL_SUBMIT
    interaction_type = payload.get("type", 0)
    if interaction_type in (2, 3, 5):
        result = await _discord_handler.handle_message(payload)
        # Acknowledge the interaction (required within 3 seconds)
        return {
            "type": 5,  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE
            "data": {"flags": 64},  # Ephemeral
        }

    return {"ok": True}
