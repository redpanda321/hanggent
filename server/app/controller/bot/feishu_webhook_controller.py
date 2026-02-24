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
Feishu (Lark) Webhook Controller — handles incoming events from
the Feishu/Lark Event Subscription.

Feishu sends event callbacks via HTTP POST.  The first callback is a
``url_verification`` challenge.  Subsequent events are wrapped in an
encrypted envelope (if ``encrypt_key`` is set) or plain JSON.

The Feishu app needs:
  * Event Subscription URL: ``https://your-domain/webhook/feishu``
  * Event: ``im.message.receive_v1`` (receive messages)
  * Permissions: ``im:message``, ``im:message.group_at_msg``, ``im:message.p2p_msg``

Routes:
  POST /webhook/feishu — Feishu event subscription endpoint
"""

import hashlib
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.component import im_channel_config
from app.controller.bot.base_channel_handler import BaseChannelHandler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Feishu Webhook"])

FEISHU_APP_ID = os.getenv("HANGGENT_FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("HANGGENT_FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.getenv("HANGGENT_FEISHU_VERIFY_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("HANGGENT_FEISHU_ENCRYPT_KEY", "")


def _decrypt_feishu_event(encrypt: str) -> dict:
    """Decrypt Feishu encrypted event body.

    Uses AES-256-CBC with the encrypt_key.
    """
    if not FEISHU_ENCRYPT_KEY:
        raise ValueError("Feishu encrypt_key not configured")
    try:
        import base64
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        key = hashlib.sha256(FEISHU_ENCRYPT_KEY.encode()).digest()
        buf = base64.b64decode(encrypt)
        iv = buf[:16]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(buf[16:]) + decryptor.finalize()
        # PKCS7 unpadding
        pad_len = plaintext[-1]
        plaintext = plaintext[:-pad_len]
        return json.loads(plaintext.decode())
    except ImportError:
        logger.error("cryptography package not installed — cannot decrypt Feishu events")
        raise
    except Exception as e:
        logger.error("Failed to decrypt Feishu event: %s", e)
        raise


def _get_tenant_access_token() -> str | None:
    """Get a Feishu tenant_access_token for sending messages."""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        return None
    import httpx
    try:
        resp = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
            timeout=10.0,
        )
        data = resp.json()
        if data.get("code") == 0:
            return data["tenant_access_token"]
    except Exception as e:
        logger.warning("Failed to get Feishu tenant_access_token: %s", e)
    return None


class FeishuHandler(BaseChannelHandler):
    """Feishu/Lark implementation of the base channel handler."""

    channel_type = "feishu"

    def extract_user_id(self, payload: dict) -> str | None:
        """Extract Feishu open_id from event payload."""
        # Event v2 format: header + event
        event = payload.get("event") or {}
        sender = event.get("sender") or {}
        sender_id = sender.get("sender_id") or {}
        return sender_id.get("open_id")

    def extract_username(self, payload: dict) -> str | None:
        event = payload.get("event") or {}
        sender = event.get("sender") or {}
        sender_id = sender.get("sender_id") or {}
        return sender_id.get("open_id")  # Use open_id as username fallback

    def extract_text(self, payload: dict) -> str:
        event = payload.get("event") or {}
        message = event.get("message") or {}
        content = message.get("content", "{}")
        try:
            parsed = json.loads(content)
            return parsed.get("text", "")
        except (json.JSONDecodeError, TypeError):
            return ""

    def extract_metadata(self, payload: dict) -> dict[str, Any] | None:
        meta: dict[str, Any] = {}
        event = payload.get("event") or {}
        message = event.get("message") or {}
        if message.get("chat_id"):
            meta["chat_id"] = message["chat_id"]
        if message.get("chat_type"):
            meta["chat_type"] = message["chat_type"]
        if message.get("message_type"):
            meta["message_type"] = message["message_type"]
        header = payload.get("header") or {}
        if header.get("tenant_key"):
            meta["tenant_key"] = header["tenant_key"]
        return meta or None

    async def send_reply(self, channel_user_id: str, text: str) -> None:
        """Send a message to a Feishu user via open_id."""
        token = _get_tenant_access_token()
        if not token:
            return
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages",
                    params={"receive_id_type": "open_id"},
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": channel_user_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": text}),
                    },
                )
        except Exception as e:
            logger.warning("Failed to send Feishu message to %s: %s", channel_user_id, e)


_feishu_handler = FeishuHandler()


@router.post("/webhook/feishu", name="feishu webhook")
async def feishu_webhook(request: Request):
    """Receive Feishu/Lark event subscription callbacks."""
    if not im_channel_config.is_channel_enabled("feishu"):
        raise HTTPException(404, detail="Feishu channel not enabled")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")

    # Handle encrypted events
    if "encrypt" in payload:
        try:
            payload = _decrypt_feishu_event(payload["encrypt"])
        except Exception:
            raise HTTPException(400, detail="Failed to decrypt event")

    # URL verification challenge (event v1)
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # Verify token (if configured)
    if FEISHU_VERIFICATION_TOKEN:
        header = payload.get("header") or {}
        token = header.get("token") or payload.get("token")
        if token != FEISHU_VERIFICATION_TOKEN:
            raise HTTPException(401, detail="Invalid verification token")

    # Event v2: header.event_type
    header = payload.get("header") or {}
    event_type = header.get("event_type", "")

    if event_type == "im.message.receive_v1":
        event = payload.get("event") or {}
        message = event.get("message") or {}
        # Only handle p2p (DM) messages
        if message.get("chat_type") == "p2p":
            result = await _feishu_handler.handle_message(payload)
            return {"ok": True, **result}

    return {"ok": True}
