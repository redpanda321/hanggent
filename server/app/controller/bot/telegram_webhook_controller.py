"""
Telegram Webhook Controller — handles incoming updates from the shared Hanggent Telegram bot.

This controller receives Telegram webhook POST requests and routes them to the
correct user's OpenClaw gateway based on the ``ChannelUserMapping`` table.
Unknown users are **auto-registered** on first message.

Backward-compatible: still supports ``/link <CODE>`` for existing web users
who want to connect their Telegram, and ``/start`` for onboarding help.

Routes:
  POST /webhook/telegram — Telegram Bot API webhook endpoint (no auth — verified by token in URL)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, select

from app.component.database import session_make
from app.component import im_channel_config
from app.controller.bot.base_channel_handler import BaseChannelHandler
from app.model.user.channel_user_mapping import ChannelUserMapping
from app.model.user.telegram_user_mapping import TelegramLinkingCode, TelegramUserMapping
from app.model.user.user import User
from app.service import auto_registration_service, channel_mapping_service, openclaw_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telegram Webhook"])

# The shared Hanggent Telegram bot token (for webhook URL verification)
SHARED_TELEGRAM_BOT_TOKEN = os.getenv("HANGGENT_TELEGRAM_BOT_TOKEN", "")


def _extract_chat_id(update: dict) -> int | None:
    """Extract the chat_id from a Telegram update object."""
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat")
    if chat:
        return chat.get("id")
    # Callback queries
    cb = update.get("callback_query")
    if cb and cb.get("message", {}).get("chat"):
        return cb["message"]["chat"]["id"]
    return None


def _extract_text(update: dict) -> str:
    """Extract message text from a Telegram update."""
    msg = update.get("message") or update.get("edited_message") or {}
    return msg.get("text", "")


def _extract_username(update: dict) -> str | None:
    """Extract the sender's @username."""
    msg = update.get("message") or update.get("edited_message") or {}
    from_user = msg.get("from") or {}
    return from_user.get("username")


async def _send_telegram_reply(chat_id: int, text: str) -> None:
    """Send a text message back to a Telegram chat via the Bot API."""
    if not SHARED_TELEGRAM_BOT_TOKEN:
        return
    import httpx
    url = f"https://api.telegram.org/bot{SHARED_TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    except Exception as e:
        logger.warning("Failed to send Telegram reply to chat %s: %s", chat_id, e)


# ── Telegram-specific handler using the base class ──────────────────────────


class TelegramHandler(BaseChannelHandler):
    """Telegram-specific implementation of the base channel handler."""

    channel_type = "telegram"

    def extract_user_id(self, payload: dict) -> str | None:
        chat_id = _extract_chat_id(payload)
        return str(chat_id) if chat_id else None

    def extract_username(self, payload: dict) -> str | None:
        return _extract_username(payload)

    def extract_text(self, payload: dict) -> str:
        return _extract_text(payload)

    def extract_metadata(self, payload: dict) -> dict[str, Any] | None:
        msg = payload.get("message") or payload.get("edited_message") or {}
        from_user = msg.get("from") or {}
        meta: dict[str, Any] = {}
        if from_user.get("first_name"):
            meta["first_name"] = from_user["first_name"]
        if from_user.get("last_name"):
            meta["last_name"] = from_user["last_name"]
        if from_user.get("language_code"):
            meta["language_code"] = from_user["language_code"]
        return meta or None

    async def send_reply(self, channel_user_id: str, text: str) -> None:
        await _send_telegram_reply(int(channel_user_id), text)


_telegram_handler = TelegramHandler()


async def _handle_link_command(chat_id: int, code_str: str, username: str | None) -> None:
    """Handle the /link command — link a Telegram chat to a Hanggent user."""
    s = session_make()
    try:
        # Find the linking code
        linking = s.exec(
            select(TelegramLinkingCode)
            .where(TelegramLinkingCode.code == code_str.strip())
            .where(TelegramLinkingCode.used == False)
        ).first()

        if not linking:
            await _send_telegram_reply(chat_id, "❌ Invalid or expired linking code. Please generate a new one in Hanggent Settings → Channels → Telegram.")
            return

        # Check expiry
        now = datetime.now(timezone.utc)
        expires = linking.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
            linking.used = True
            s.add(linking)
            s.commit()
            await _send_telegram_reply(chat_id, "⏰ This linking code has expired. Please generate a new one.")
            return

        user_id = linking.user_id

        # Check if this chat_id is already mapped to another user
        existing = s.exec(
            select(TelegramUserMapping)
            .where(TelegramUserMapping.telegram_chat_id == chat_id)
        ).first()

        if existing:
            if existing.user_id == user_id:
                await _send_telegram_reply(chat_id, "✅ This Telegram chat is already linked to your Hanggent account!")
            else:
                # Re-link to new user
                existing.user_id = user_id
                existing.telegram_username = username
                existing.linked_at = datetime.utcnow()
                s.add(existing)
        else:
            mapping = TelegramUserMapping(
                user_id=user_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
            )
            s.add(mapping)

        # Mark code as used
        linking.used = True
        s.add(linking)

        # Update user's bot_channels to include telegram shared mode
        user = s.get(User, user_id)
        if user:
            channels = dict(user.bot_channels or {})
            channels["telegram"] = {"mode": "shared", "chatId": chat_id}
            user.bot_channels = channels
            s.add(user)

        s.commit()

        # Also create/update the generic ChannelUserMapping for consistency
        existing_generic = channel_mapping_service.find_user_by_channel(
            "telegram", str(chat_id), s=s,
        )
        if existing_generic:
            if existing_generic.user_id != user_id:
                existing_generic.user_id = user_id
                existing_generic.channel_username = username
                channel_mapping_service.update_mapping(
                    existing_generic, channel_username=username, s=s,
                )
        else:
            channel_mapping_service.create_mapping(
                user_id=user_id,
                channel_type="telegram",
                channel_user_id=str(chat_id),
                channel_username=username,
                auto_registered=False,
                s=s,
            )

        await _send_telegram_reply(
            chat_id,
            "✅ *Linked successfully!* Your Telegram is now connected to your Hanggent account.\n\n"
            "You can now send messages here and they'll be processed by your AI assistant.",
        )

        # Auto-start the gateway if not running
        if user:
            asyncio.create_task(
                openclaw_service.ensure_bot_running_fire_and_forget(user_id, dict(user.bot_channels or {}))
            )

    except Exception as e:
        logger.error("Failed to process /link command: %s", e, exc_info=True)
        await _send_telegram_reply(chat_id, "❌ An error occurred. Please try again.")
    finally:
        s.close()


async def _route_to_user_gateway(user_id: int, update: dict) -> None:
    """Forward a Telegram update to the user's OpenClaw gateway via supervisor proxy."""
    try:
        # Ensure gateway is running (auto-start if reaped by idle timeout)
        await openclaw_service.ensure_bot_running(user_id)

        # Forward the update to the gateway's Telegram webhook handler
        await openclaw_service.proxy_to_bot(
            user_id,
            "webhook/telegram",
            method="POST",
            body=update,
        )
    except Exception as e:
        logger.error("Failed to route Telegram update to user %s: %s", user_id, e)


@router.post("/webhook/telegram", name="telegram webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook updates for the shared Hanggent bot.

    No auth required — Telegram sends updates to this URL.
    Production should use a secret token in the webhook URL for verification.
    """
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")

    chat_id = _extract_chat_id(update)
    if not chat_id:
        # Non-message update (e.g., channel_post) — ignore
        return {"ok": True}

    text = _extract_text(update)
    username = _extract_username(update)

    # Handle /start command
    if text.strip().lower() == "/start":
        await _send_telegram_reply(
            chat_id,
            "👋 *Welcome to Hanggent AI!*\n\n"
            "Just send me a message and I'll be your AI assistant!\n\n"
            "🔗 *Already have a Hanggent account?*\n"
            "Link it with: Settings → Channels → Telegram → Generate Code → `/link YOUR_CODE`",
        )
        return {"ok": True}

    # Handle /link <code> command (backward compat for linking existing accounts)
    if text.strip().lower().startswith("/link"):
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await _send_telegram_reply(chat_id, "Usage: `/link YOUR_CODE`\n\nGet your code from Hanggent Settings → Channels → Telegram.")
            return {"ok": True}
        asyncio.create_task(_handle_link_command(chat_id, parts[1], username))
        return {"ok": True}

    # ── Regular message — auto-register (or look up) and route ──────────
    result = await _telegram_handler.handle_message(update)
    return {"ok": True, **result}


@router.post("/webhook/telegram/{token}", name="telegram webhook with token")
async def telegram_webhook_with_token(token: str, request: Request):
    """Telegram webhook with secret token in URL for verification."""
    if SHARED_TELEGRAM_BOT_TOKEN and token != SHARED_TELEGRAM_BOT_TOKEN:
        raise HTTPException(403, detail="Invalid webhook token")
    return await telegram_webhook(request)
