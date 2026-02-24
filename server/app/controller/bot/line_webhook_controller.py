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
LINE Webhook Controller — handles incoming events from the LINE Messaging API.

LINE sends webhook events (message, follow, unfollow, etc.) via HTTP POST.
Request signature is verified with the Channel Secret (HMAC-SHA256, base64).

The LINE channel needs:
  * Webhook URL: ``https://your-domain/webhook/line``
  * Channel Access Token (long-lived)
  * Channel Secret (for signature verification)

Routes:
  POST /webhook/line — LINE Messaging API events
"""

import base64
import hashlib
import hmac
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.component import im_channel_config
from app.controller.bot.base_channel_handler import BaseChannelHandler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["LINE Webhook"])

LINE_CHANNEL_SECRET = os.getenv("HANGGENT_LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("HANGGENT_LINE_ACCESS_TOKEN", "")


def _verify_line_signature(body: bytes, signature: str) -> bool:
    """Verify LINE webhook signature."""
    if not LINE_CHANNEL_SECRET:
        return True
    computed = base64.b64encode(
        hmac.new(
            LINE_CHANNEL_SECRET.encode(),
            body,
            hashlib.sha256,
        ).digest()
    ).decode()
    return hmac.compare_digest(computed, signature)


class LINEHandler(BaseChannelHandler):
    """LINE Messaging API implementation of the base channel handler."""

    channel_type = "line"

    def extract_user_id(self, payload: dict) -> str | None:
        """Extract LINE userId from webhook event."""
        for event in payload.get("events", []):
            source = event.get("source", {})
            if source.get("type") == "user":
                return source.get("userId")
        return None

    def extract_username(self, payload: dict) -> str | None:
        # LINE doesn't include display name in webhooks; need Profile API
        return None

    def extract_text(self, payload: dict) -> str:
        for event in payload.get("events", []):
            if event.get("type") == "message":
                msg = event.get("message", {})
                if msg.get("type") == "text":
                    return msg.get("text", "")
        return ""

    def extract_metadata(self, payload: dict) -> dict[str, Any] | None:
        meta: dict[str, Any] = {}
        for event in payload.get("events", []):
            if event.get("replyToken"):
                meta["replyToken"] = event["replyToken"]
            if event.get("timestamp"):
                meta["timestamp"] = event["timestamp"]
            if event.get("type"):
                meta["event_type"] = event["type"]
        return meta or None

    async def send_reply(self, channel_user_id: str, text: str) -> None:
        """Send a push message to a LINE user."""
        if not LINE_CHANNEL_ACCESS_TOKEN:
            return
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    "https://api.line.me/v2/bot/message/push",
                    headers={
                        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "to": channel_user_id,
                        "messages": [{"type": "text", "text": text}],
                    },
                )
        except Exception as e:
            logger.warning("Failed to send LINE push message to %s: %s", channel_user_id, e)


_line_handler = LINEHandler()


@router.post("/webhook/line", name="line webhook")
async def line_webhook(request: Request):
    """Receive LINE Messaging API webhook events."""
    if not im_channel_config.is_channel_enabled("line"):
        raise HTTPException(404, detail="LINE channel not enabled")

    body = await request.body()
    signature = request.headers.get("x-line-signature", "")

    if not _verify_line_signature(body, signature):
        raise HTTPException(401, detail="Invalid LINE signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")

    # Process message events only
    events = payload.get("events", [])
    message_events = [e for e in events if e.get("type") == "message"]

    if message_events:
        result = await _line_handler.handle_message(payload)
        return {"ok": True, **result}

    return {"ok": True}
