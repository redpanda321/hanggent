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
WhatsApp Webhook Controller — handles incoming messages from the
WhatsApp Business Cloud API.

Meta sends webhook notifications to a verified callback URL.
Verification is done via a GET with ``hub.verify_token`` / ``hub.challenge``.
Incoming messages arrive as POST with a ``messages`` array.

The WhatsApp Business app needs:
  * Webhook URL: ``https://your-domain/webhook/whatsapp``
  * Verify Token: set in ``HANGGENT_WHATSAPP_VERIFY``
  * Subscribed fields: ``messages``

Routes:
  GET  /webhook/whatsapp — Meta verification challenge
  POST /webhook/whatsapp — Incoming message events
"""

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.component import im_channel_config
from app.controller.bot.base_channel_handler import BaseChannelHandler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WhatsApp Webhook"])

WHATSAPP_VERIFY_TOKEN = os.getenv("HANGGENT_WHATSAPP_VERIFY", "")
WHATSAPP_API_TOKEN = os.getenv("HANGGENT_WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("HANGGENT_WHATSAPP_PHONE_ID", "")


class WhatsAppHandler(BaseChannelHandler):
    """WhatsApp Business API implementation of the base channel handler."""

    channel_type = "whatsapp"

    def extract_user_id(self, payload: dict) -> str | None:
        """Extract sender phone number (E.164) from WhatsApp Cloud API payload."""
        # WhatsApp Cloud API structure:
        # entry[].changes[].value.messages[].from
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    return msg.get("from")  # Phone number in E.164
        return None

    def extract_username(self, payload: dict) -> str | None:
        """Extract the WhatsApp display name from contacts."""
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for contact in value.get("contacts", []):
                    profile = contact.get("profile", {})
                    return profile.get("name")
        return None

    def extract_text(self, payload: dict) -> str:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    if msg.get("type") == "text":
                        return msg.get("text", {}).get("body", "")
        return ""

    def extract_metadata(self, payload: dict) -> dict[str, Any] | None:
        meta: dict[str, Any] = {}
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                md = value.get("metadata", {})
                if md.get("phone_number_id"):
                    meta["phone_number_id"] = md["phone_number_id"]
                if md.get("display_phone_number"):
                    meta["display_phone_number"] = md["display_phone_number"]
                for msg in value.get("messages", []):
                    if msg.get("type"):
                        meta["message_type"] = msg["type"]
                    if msg.get("timestamp"):
                        meta["timestamp"] = msg["timestamp"]
        return meta or None

    async def send_reply(self, channel_user_id: str, text: str) -> None:
        """Send a text message via WhatsApp Business Cloud API."""
        if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            return
        import httpx
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    url,
                    headers={"Authorization": f"Bearer {WHATSAPP_API_TOKEN}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": channel_user_id,
                        "type": "text",
                        "text": {"body": text},
                    },
                )
        except Exception as e:
            logger.warning("Failed to send WhatsApp reply to %s: %s", channel_user_id, e)


_whatsapp_handler = WhatsAppHandler()


@router.get("/webhook/whatsapp", name="whatsapp verification")
async def whatsapp_verify(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification challenge (GET)."""
    if not im_channel_config.is_channel_enabled("whatsapp"):
        raise HTTPException(404, detail="WhatsApp channel not enabled")

    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge) if hub_challenge else ""
    raise HTTPException(403, detail="Verification failed")


@router.post("/webhook/whatsapp", name="whatsapp webhook")
async def whatsapp_webhook(request: Request):
    """Receive WhatsApp Business API webhook events."""
    if not im_channel_config.is_channel_enabled("whatsapp"):
        raise HTTPException(404, detail="WhatsApp channel not enabled")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")

    # Check for actual messages (not status updates)
    has_messages = False
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if value.get("messages"):
                has_messages = True
                break

    if has_messages:
        result = await _whatsapp_handler.handle_message(payload)
        return {"ok": True, **result}

    return {"ok": True}
