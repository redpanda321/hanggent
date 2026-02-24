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
Slack Webhook Controller — handles incoming events from the shared
Hanggent Slack app via the Events API.

Slack sends HTTP POST requests for events the app is subscribed to.
We handle ``url_verification`` (challenge), and ``event_callback``
for ``message`` events in DM channels (``im`` type).

The Slack app needs:
  * Event Subscriptions → Request URL: ``https://your-domain/webhook/slack``
  * Bot Token Scopes: ``im:read``, ``im:history``, ``chat:write``
  * Subscribe to bot events: ``message.im``

Routes:
  POST /webhook/slack — Slack Events API endpoint
"""

import hashlib
import hmac
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.component import im_channel_config
from app.controller.bot.base_channel_handler import BaseChannelHandler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Slack Webhook"])

SLACK_SIGNING_SECRET = os.getenv("HANGGENT_SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("HANGGENT_SLACK_BOT_TOKEN", "")


def _verify_slack_signature(body: bytes, signature: str, timestamp: str) -> bool:
    """Verify Slack request signature (v0 HMAC-SHA256)."""
    if not SLACK_SIGNING_SECRET:
        return True
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:  # 5 minute window
            return False
    except (ValueError, TypeError):
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


class SlackHandler(BaseChannelHandler):
    """Slack-specific implementation of the base channel handler."""

    channel_type = "slack"

    def extract_user_id(self, payload: dict) -> str | None:
        """Extract Slack user ID from an event payload."""
        event = payload.get("event") or {}
        # Ignore bot messages to prevent loops
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return None
        return event.get("user")

    def extract_username(self, payload: dict) -> str | None:
        event = payload.get("event") or {}
        return event.get("user")  # Slack user ID is the best we get from events

    def extract_text(self, payload: dict) -> str:
        event = payload.get("event") or {}
        return event.get("text", "")

    def extract_metadata(self, payload: dict) -> dict[str, Any] | None:
        event = payload.get("event") or {}
        meta: dict[str, Any] = {}
        if event.get("channel"):
            meta["channel"] = event["channel"]
        if event.get("channel_type"):
            meta["channel_type"] = event["channel_type"]
        if event.get("team"):
            meta["team"] = event["team"]
        return meta or None

    async def send_reply(self, channel_user_id: str, text: str) -> None:
        """Send a DM to a Slack user via chat.postMessage.

        We need to open a DM channel first, then post.
        """
        if not SLACK_BOT_TOKEN:
            return
        import httpx
        headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Open (or get) DM channel
                resp = await client.post(
                    "https://slack.com/api/conversations.open",
                    headers=headers,
                    json={"users": channel_user_id},
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning("Failed to open Slack DM: %s", data.get("error"))
                    return
                dm_channel = data["channel"]["id"]
                await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=headers,
                    json={"channel": dm_channel, "text": text},
                )
        except Exception as e:
            logger.warning("Failed to send Slack DM to %s: %s", channel_user_id, e)


_slack_handler = SlackHandler()


@router.post("/webhook/slack", name="slack webhook")
async def slack_webhook(request: Request):
    """Receive Slack Events API callbacks.

    Handles ``url_verification`` challenge and ``event_callback`` for DM messages.
    """
    if not im_channel_config.is_channel_enabled("slack"):
        raise HTTPException(404, detail="Slack channel not enabled")

    body = await request.body()
    signature = request.headers.get("x-slack-signature", "")
    timestamp = request.headers.get("x-slack-request-timestamp", "")

    if not _verify_slack_signature(body, signature, timestamp):
        raise HTTPException(401, detail="Invalid Slack signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")

    # URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # Event callback
    if payload.get("type") == "event_callback":
        event = payload.get("event") or {}
        event_type = event.get("type")

        # Only handle DM messages (channel_type == "im")
        if event_type == "message" and event.get("channel_type") == "im":
            # Ignore bot messages
            if not event.get("bot_id") and event.get("subtype") is None:
                result = await _slack_handler.handle_message(payload)
                return {"ok": True, **result}

    return {"ok": True}
