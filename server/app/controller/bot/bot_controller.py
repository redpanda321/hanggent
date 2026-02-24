"""
Bot Controller — REST API for managing per-user OpenClaw bot instances.

Routes:
  POST /bot/start     — start the user's OpenClaw gateway
  POST /bot/stop      — stop the user's OpenClaw gateway
  GET  /bot/status    — get gateway status + health
  GET  /bot/channels  — list connected messaging channels
  POST /bot/message   — send a message via a channel
  GET  /bot/health    — supervisor health (admin)
  GET  /bot/instances — list all running instances (admin)

  Channel management:
  POST   /bot/channels/connect    — connect a messaging channel (auto-starts gateway)
  POST   /bot/channels/disconnect — disconnect a messaging channel
  GET    /bot/channels/config     — get user's channel configuration
  POST   /bot/channels/telegram/link-code — generate Telegram linking code (shared bot)
"""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Any

from app.component.auth import Auth, auth, auth_must
from app.component.database import session
from app.service import channel_mapping_service, openclaw_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Bot"])


# ── Request/Response Models ─────────────────────────────────────────────────────


class BotStatusOut(BaseModel):
    userId: str | None = None
    port: int | None = None
    status: str = "stopped"
    lastActiveAt: int | None = None
    startedAt: int | None = None
    lastError: str | None = None
    health: dict | None = None


class BotMessageIn(BaseModel):
    channel: str
    to: str
    message: str


# ── Endpoints ───────────────────────────────────────────────────────────────────


@router.post("/bot/start", name="start bot", response_model=BotStatusOut)
async def start_bot(auth: Auth = Depends(auth_must)):
    """Start the authenticated user's OpenClaw gateway sub-process."""
    try:
        result = await openclaw_service.start_bot(auth.id)
        return BotStatusOut(**result)
    except Exception as e:
        logger.error(f"Failed to start bot for user {auth.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start bot: {str(e)}")


@router.post("/bot/stop", name="stop bot")
async def stop_bot(auth: Auth = Depends(auth_must)):
    """Stop the authenticated user's OpenClaw gateway sub-process."""
    try:
        result = await openclaw_service.stop_bot(auth.id)
        return result
    except Exception as e:
        logger.error(f"Failed to stop bot for user {auth.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop bot: {str(e)}")


@router.get("/bot/status", name="bot status", response_model=BotStatusOut)
async def bot_status(auth: Auth = Depends(auth_must)):
    """Get the status and health of the user's OpenClaw gateway."""
    try:
        result = await openclaw_service.get_bot_status(auth.id)
        return BotStatusOut(**result)
    except Exception as e:
        logger.error(f"Failed to get bot status for user {auth.id}: {e}")
        # If supervisor is unreachable, return stopped
        return BotStatusOut(status="stopped", lastError=str(e))


@router.get("/bot/channels", name="bot channels")
async def bot_channels(auth: Auth = Depends(auth_must)):
    """List connected messaging channels for the user's bot."""
    try:
        result = await openclaw_service.proxy_to_bot(auth.id, "channels")
        return result
    except Exception as e:
        logger.error(f"Failed to get channels for user {auth.id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to get channels: {str(e)}")


@router.get("/bot/logs", name="bot logs")
async def bot_logs(auth: Auth = Depends(auth_must)):
    """Return buffered log entries for the user's OpenClaw gateway."""
    try:
        entries = await openclaw_service.get_bot_logs(auth.id)
        return {"entries": entries}
    except Exception as e:
        logger.error(f"Failed to get logs for user {auth.id}: {e}")
        return {"entries": []}


@router.get("/bot/logs/stream", name="bot log stream")
async def bot_log_stream(
    request: Request,
    token: str | None = Query(None, description="Auth token (EventSource cannot send headers)"),
    auth_dep: Auth | None = Depends(auth),
):
    """Stream real-time log entries for the user's OpenClaw gateway (SSE).

    Accepts authentication via either:
    - Standard ``Authorization: Bearer <token>`` header (used by fetch)
    - ``?token=`` query parameter (required by ``EventSource`` which cannot set headers)
    """
    from sqlmodel import Session
    from app.component.database import session_make

    # Resolve user from header-based auth first, fall back to token query param
    user_auth = auth_dep
    if user_auth is None and token:
        try:
            user_auth = Auth.decode_token(token)
            # Attach user object
            s = session_make()
            try:
                from app.model.user.user import User
                user_auth._user = s.get(User, user_auth.id)
            finally:
                s.close()
        except Exception:
            user_auth = None

    if user_auth is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user_auth.id

    async def _generator():
        try:
            async for chunk in openclaw_service.stream_bot_logs(user_id):
                yield chunk
        except Exception as e:
            logger.error(f"Log stream error for user {user_id}: {e}")
            yield f'data: {{"ts": 0, "level": "error", "msg": "Stream disconnected"}}\n\n'

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/bot/message", name="send bot message")
async def send_message(body: BotMessageIn, auth: Auth = Depends(auth_must)):
    """Send a message via the user's OpenClaw gateway."""
    try:
        result = await openclaw_service.proxy_to_bot(
            auth.id,
            "messages/send",
            method="POST",
            body={"channel": body.channel, "to": body.to, "message": body.message},
        )
        return result
    except Exception as e:
        logger.error(f"Failed to send message for user {auth.id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to send message: {str(e)}")


@router.get("/bot/proxy/{path:path}", name="bot proxy GET")
async def proxy_get(path: str, auth: Auth = Depends(auth_must)):
    """Proxy a GET request to the user's OpenClaw gateway."""
    try:
        result = await openclaw_service.proxy_to_bot(auth.id, path)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/bot/proxy/{path:path}", name="bot proxy POST")
async def proxy_post(path: str, auth: Auth = Depends(auth_must)):
    """Proxy a POST request to the user's OpenClaw gateway."""
    try:
        result = await openclaw_service.proxy_to_bot(auth.id, path, method="POST")
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Control UI Proxy ────────────────────────────────────────────────────────────


@router.get("/bot/ui/{path:path}", name="bot UI proxy GET")
async def proxy_ui_get(
    path: str,
    request: Request,
    token: str | None = Query(None, description="Auth token (iframe cannot send headers)"),
    auth_dep: Auth | None = Depends(auth),
):
    """Proxy a GET request to the user's OpenClaw gateway Control UI.

    Serves raw HTTP responses (HTML, JS, CSS, images) with the original
    Content-Type.  Strips X-Frame-Options and CSP headers so the UI can
    be embedded in an iframe.

    Accepts authentication via either:
    - Standard ``Authorization: Bearer <token>`` header
    - ``?token=`` query parameter (required by iframes which cannot set headers)
    """
    from app.component.database import session_make

    # Resolve user from header-based auth first, fall back to token query param
    user_auth = auth_dep
    if user_auth is None and token:
        try:
            user_auth = Auth.decode_token(token)
            s = session_make()
            try:
                from app.model.user.user import User
                user_auth._user = s.get(User, user_auth.id)
            finally:
                s.close()
        except Exception:
            user_auth = None

    if user_auth is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Forward query string (minus the auth token) so the OpenClaw UI
        # receives navigation params without leaking credentials.
        full_path = path or "index.html"
        filtered_qs = "&".join(
            f"{k}={v}"
            for k, v in request.query_params.multi_items()
            if k != "token"
        )
        if filtered_qs:
            full_path = f"{full_path}?{filtered_qs}"
        status_code, headers, body = await openclaw_service.proxy_to_bot_raw(
            user_auth.id, full_path,
        )
        from starlette.responses import Response
        return Response(content=body, status_code=status_code, headers=headers)
    except Exception as e:
        logger.error(f"UI proxy GET failed for user {user_auth.id}, path={path}: {e}")
        raise HTTPException(status_code=502, detail=f"UI proxy error: {str(e)}")


@router.post("/bot/ui/{path:path}", name="bot UI proxy POST")
async def proxy_ui_post(
    path: str,
    request: Request,
    token: str | None = Query(None, description="Auth token (iframe cannot send headers)"),
    auth_dep: Auth | None = Depends(auth),
):
    """Proxy a POST request to the user's OpenClaw gateway Control UI.

    Accepts authentication via either:
    - Standard ``Authorization: Bearer <token>`` header
    - ``?token=`` query parameter (required by iframes which cannot set headers)
    """
    from app.component.database import session_make

    # Resolve user from header-based auth first, fall back to token query param
    user_auth = auth_dep
    if user_auth is None and token:
        try:
            user_auth = Auth.decode_token(token)
            s = session_make()
            try:
                from app.model.user.user import User
                user_auth._user = s.get(User, user_auth.id)
            finally:
                s.close()
        except Exception:
            user_auth = None

    if user_auth is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        body = await request.body()
        req_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "authorization", "cookie")
        }
        status_code, headers, resp_body = await openclaw_service.proxy_to_bot_raw(
            user_auth.id, path, method="POST", body=body, headers=req_headers,
        )
        from starlette.responses import Response
        return Response(content=resp_body, status_code=status_code, headers=headers)
    except Exception as e:
        logger.error(f"UI proxy POST failed for user {user_auth.id}, path={path}: {e}")
        raise HTTPException(status_code=502, detail=f"UI proxy error: {str(e)}")


# ── Channel Management Endpoints ───────────────────────────────────────────────

SUPPORTED_CHANNELS = {
    "telegram", "discord", "slack", "whatsapp", "webchat",
    "line", "feishu", "signal", "irc", "matrix", "msteams", "googlechat",
}


class ChannelConnectIn(BaseModel):
    channel: str
    config: dict[str, Any] = {}


class ChannelDisconnectIn(BaseModel):
    channel: str


class ChannelConfigOut(BaseModel):
    channels: dict[str, Any] = {}
    bot_status: str = "stopped"


@router.post("/bot/channels/connect", name="connect channel")
async def connect_channel(
    body: ChannelConnectIn,
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """Connect a messaging channel and auto-start the OpenClaw gateway.

    Saves channel config to user.bot_channels, writes openclaw.json via
    supervisor, and starts/reloads the gateway.
    """
    if body.channel not in SUPPORTED_CHANNELS:
        raise HTTPException(400, detail=f"Unsupported channel: {body.channel}. Supported: {SUPPORTED_CHANNELS}")

    from app.model.user.user import User

    user = s.get(User, auth.id)
    if not user:
        raise HTTPException(404, detail="User not found")

    # Merge channel config into existing bot_channels
    channels = dict(user.bot_channels or {})
    channels[body.channel] = body.config
    user.bot_channels = channels
    s.add(user)
    s.commit()
    s.refresh(user)

    # Create ChannelUserMapping if channel config contains a channel_user_id
    channel_user_id = body.config.get("channel_user_id") or body.config.get("chatId")
    if channel_user_id:
        existing = channel_mapping_service.find_user_by_channel(
            body.channel, str(channel_user_id), s=s,
        )
        if not existing:
            channel_mapping_service.create_mapping(
                user_id=user.id,
                channel_type=body.channel,
                channel_user_id=str(channel_user_id),
                s=s,
            )

    # Write config and ensure gateway is running (or reload if already running)
    try:
        result = await openclaw_service.ensure_bot_running(auth.id, channels)
        return {
            "status": "connected",
            "channel": body.channel,
            "bot_status": result.get("status", "starting"),
        }
    except Exception as e:
        logger.error(f"Failed to start bot after channel connect for user {auth.id}: {e}")
        # Channel config is saved even if gateway fails to start
        return {
            "status": "config_saved",
            "channel": body.channel,
            "bot_status": "error",
            "error": str(e),
        }


@router.post("/bot/channels/disconnect", name="disconnect channel")
async def disconnect_channel(
    body: ChannelDisconnectIn,
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """Disconnect a messaging channel. Stops gateway if no channels remain."""
    from app.model.user.user import User

    user = s.get(User, auth.id)
    if not user:
        raise HTTPException(404, detail="User not found")

    channels = dict(user.bot_channels or {})
    removed = channels.pop(body.channel, None)
    user.bot_channels = channels if channels else None
    s.add(user)
    s.commit()

    # Soft-delete ChannelUserMapping for this channel
    mapping = channel_mapping_service.find_mappings_by_channel_type(
        user.id, body.channel, s=s,
    )
    if mapping:
        channel_mapping_service.delete_mapping(mapping, s=s)

    if not channels:
        # No channels left — stop the gateway
        try:
            await openclaw_service.stop_bot(auth.id)
        except Exception:
            pass
        return {"status": "disconnected", "channel": body.channel, "bot_status": "stopped"}

    # Still have other channels — update config and reload
    try:
        await openclaw_service.write_user_config(auth.id, channels)
        await openclaw_service.reload_user_config(auth.id)
    except Exception:
        pass

    return {"status": "disconnected", "channel": body.channel, "bot_status": "running"}


@router.get("/bot/channels/config", name="channel config")
async def get_channel_config(
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """Get the user's channel configuration with tokens masked."""
    from app.model.user.user import User

    user = s.get(User, auth.id)
    if not user:
        raise HTTPException(404, detail="User not found")

    channels = dict(user.bot_channels or {})

    # Mask sensitive tokens for display
    masked = {}
    for ch_name, ch_cfg in channels.items():
        ch_copy = dict(ch_cfg)
        for key in ("botToken", "signingSecret", "appToken"):
            if key in ch_copy and ch_copy[key]:
                val = ch_copy[key]
                ch_copy[key] = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"
        masked[ch_name] = ch_copy

    # Get bot status
    bot_status = "stopped"
    try:
        status_resp = await openclaw_service.get_bot_status(auth.id)
        bot_status = status_resp.get("status", "stopped")
    except Exception:
        pass

    return ChannelConfigOut(channels=masked, bot_status=bot_status)


@router.post("/bot/channels/telegram/link-code", name="telegram link code")
async def generate_telegram_link_code(
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """Generate a 6-digit linking code for the shared Hanggent Telegram bot.

    The user sends ``/link <CODE>`` to @HanggentBot on Telegram.
    The webhook handler will validate the code and create the mapping.
    The code expires in 5 minutes.
    """
    from app.model.user.telegram_user_mapping import TelegramLinkingCode

    # Invalidate any existing unused codes for this user
    existing = s.exec(
        select(TelegramLinkingCode)
        .where(TelegramLinkingCode.user_id == auth.id)
        .where(TelegramLinkingCode.used == False)
    ).all()
    for old in existing:
        old.used = True
        s.add(old)

    # Generate a new 6-digit code
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    linking = TelegramLinkingCode(
        user_id=auth.id,
        code=code,
        expires_at=expires_at,
    )
    s.add(linking)
    s.commit()

    return {
        "code": code,
        "expires_at": expires_at.isoformat(),
        "instructions": "Send /link {code} to @HanggentBot on Telegram to link your account.",
    }


# ── Generic Channel Link-Code ──────────────────────────────────────────────────


class ChannelLinkCodeIn(BaseModel):
    channel: str


class ChannelLinkCodeOut(BaseModel):
    code: str
    channel: str
    expires_at: str
    instructions: str


@router.post(
    "/bot/channels/{channel}/link-code",
    name="channel link code",
    response_model=ChannelLinkCodeOut,
)
async def generate_channel_link_code(
    channel: str,
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """Generate a 6-digit linking code for *any* IM channel.

    The user sends ``/link <CODE>`` (or equivalent) in the target IM app.
    The webhook handler validates the code and creates a ChannelUserMapping.
    The code expires in 5 minutes.
    """
    if channel not in SUPPORTED_CHANNELS:
        raise HTTPException(400, detail=f"Unsupported channel: {channel}")

    from app.model.user.channel_user_mapping import ChannelLinkingCode

    # Invalidate existing unused codes for this user + channel
    existing = s.exec(
        select(ChannelLinkingCode)
        .where(ChannelLinkingCode.user_id == auth.id)
        .where(ChannelLinkingCode.channel_type == channel)
        .where(ChannelLinkingCode.used == False)
    ).all()
    for old in existing:
        old.used = True
        s.add(old)

    # Generate a new 6-digit code
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    linking = ChannelLinkingCode(
        user_id=auth.id,
        channel_type=channel,
        code=code,
        expires_at=expires_at,
    )
    s.add(linking)
    s.commit()

    channel_names = {
        "telegram": "@HanggentBot on Telegram",
        "discord": "the Hanggent bot on Discord",
        "slack": "the Hanggent app on Slack",
        "whatsapp": "the Hanggent number on WhatsApp",
        "line": "the Hanggent account on LINE",
        "feishu": "the Hanggent bot on Feishu/Lark",
    }
    display = channel_names.get(channel, f"the Hanggent bot on {channel}")

    return ChannelLinkCodeOut(
        code=code,
        channel=channel,
        expires_at=expires_at.isoformat(),
        instructions=f"Send /link {code} to {display} to link your account.",
    )


# ── Channel Mappings ────────────────────────────────────────────────────────────


class ChannelMappingOut(BaseModel):
    id: int
    channel_type: str
    channel_user_id: str
    channel_username: str | None = None
    auto_registered: bool = False
    linked_at: str | None = None


@router.get("/bot/channels/mappings", name="list channel mappings")
async def list_channel_mappings(
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """List all IM channel mappings for the authenticated user."""
    mappings = channel_mapping_service.find_mappings_by_user(auth.id, s=s)
    return [
        ChannelMappingOut(
            id=m.id,
            channel_type=m.channel_type,
            channel_user_id=m.channel_user_id,
            channel_username=m.channel_username,
            auto_registered=m.auto_registered,
            linked_at=m.linked_at.isoformat() if m.linked_at else None,
        )
        for m in mappings
    ]


@router.delete("/bot/channels/mappings/{mapping_id}", name="delete channel mapping")
async def delete_channel_mapping(
    mapping_id: int,
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """Remove a specific channel mapping (unlink an IM identity)."""
    from app.model.user.channel_user_mapping import ChannelUserMapping

    mapping = s.get(ChannelUserMapping, mapping_id)
    if not mapping or mapping.deleted_at is not None:
        raise HTTPException(404, detail="Mapping not found")
    if mapping.user_id != auth.id:
        raise HTTPException(403, detail="Not your mapping")

    channel_mapping_service.delete_mapping(mapping, s=s)
    return {"status": "deleted", "mapping_id": mapping_id}


# ── Account Merge / Re-Link ────────────────────────────────────────────────────


class AccountMergeIn(BaseModel):
    """Merge an auto-registered IM-only account into this authenticated account."""
    channel_type: str
    channel_user_id: str


@router.post("/bot/channels/merge", name="merge IM account")
async def merge_im_account(
    body: AccountMergeIn,
    auth: Auth = Depends(auth_must),
    s: Session = Depends(session),
):
    """Merge an auto-registered IM account into the current web account.

    When a user first messaged via IM, an auto-registered account was
    created.  If they then sign up through the web UI and want to claim
    their IM history, they call this endpoint.

    1. Validates the IM identity exists and was auto-registered.
    2. Re-points the ChannelUserMapping to the authenticated user.
    3. Copies ``bot_channels`` config to the authenticated user.
    4. Marks the old auto-registered user as merged (sets ``deleted_at``).
    """
    from app.model.user.user import User

    mapping = channel_mapping_service.find_user_by_channel(
        body.channel_type, body.channel_user_id, s=s,
    )
    if not mapping:
        raise HTTPException(404, detail="No mapping found for that IM identity")

    if mapping.user_id == auth.id:
        return {"status": "already_linked", "message": "This IM identity is already linked to your account."}

    if not mapping.auto_registered:
        raise HTTPException(
            409,
            detail="That IM identity is linked to a non-auto-registered account. "
                   "The other user must unlink it first.",
        )

    old_user = s.get(User, mapping.user_id)

    # Re-point mapping to current user
    mapping.user_id = auth.id
    mapping.auto_registered = False  # now explicitly linked
    s.add(mapping)

    # Merge bot_channels config
    current_user = s.get(User, auth.id)
    if not current_user:
        raise HTTPException(404, detail="User not found")

    merged_channels = dict(current_user.bot_channels or {})
    if old_user and old_user.bot_channels:
        for ch, cfg in old_user.bot_channels.items():
            if ch not in merged_channels:
                merged_channels[ch] = cfg
    current_user.bot_channels = merged_channels if merged_channels else None
    s.add(current_user)

    # Mark old auto-registered user as merged
    if old_user:
        old_user.deleted_at = datetime.now(timezone.utc)
        s.add(old_user)

    s.commit()

    # Restart gateway with merged config
    try:
        if merged_channels:
            await openclaw_service.ensure_bot_running(auth.id, merged_channels)
    except Exception:
        logger.warning("Failed to restart gateway after account merge for user %s", auth.id)

    return {
        "status": "merged",
        "channel_type": body.channel_type,
        "channel_user_id": body.channel_user_id,
        "message": "IM identity has been linked to your account.",
    }


# ── Admin Endpoints ─────────────────────────────────────────────────────────────

import os as _os
_ADMIN_USER_IDS: set[int] = set()
try:
    _raw = _os.getenv("ADMIN_USER_IDS", "")
    if _raw:
        _ADMIN_USER_IDS = {int(x.strip()) for x in _raw.split(",") if x.strip()}
except Exception:
    pass


def _require_admin(auth: Auth) -> None:
    """Raise 403 if the authenticated user is not in the ADMIN_USER_IDS list."""
    if _ADMIN_USER_IDS and auth.id not in _ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/bot/admin/health", name="supervisor health")
async def supervisor_health(auth: Auth = Depends(auth_must)):
    """Get the OpenClaw supervisor health (admin only)."""
    _require_admin(auth)
    try:
        result = await openclaw_service.get_supervisor_health()
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Supervisor unreachable: {str(e)}")


@router.get("/bot/admin/instances", name="list all bot instances")
async def list_instances(auth: Auth = Depends(auth_must)):
    """List all running OpenClaw instances (admin only)."""
    _require_admin(auth)
    try:
        result = await openclaw_service.list_bots()
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
