"""
OpenClaw Service — manages per-user OpenClaw gateway instances
via the OpenClaw Supervisor Management API.

The supervisor runs as a separate K8s pod (openclaw-supervisor)
and spawns per-user gateway sub-processes with isolated state dirs.
"""

import asyncio
import json
import os
import logging
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# Supervisor URL (K8s ClusterIP service)
SUPERVISOR_URL = os.getenv("OPENCLAW_SUPERVISOR_URL", "http://openclaw-supervisor:18800")
SUPERVISOR_TOKEN = os.getenv("OPENCLAW_SUPERVISOR_TOKEN", "")
REQUEST_TIMEOUT = 30.0


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if SUPERVISOR_TOKEN:
        h["Authorization"] = f"Bearer {SUPERVISOR_TOKEN}"
    return h


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=SUPERVISOR_URL,
        headers=_headers(),
        timeout=REQUEST_TIMEOUT,
    )


def _extract_error(resp: httpx.Response) -> str:
    """Extract a human-readable error message from a supervisor error response."""
    try:
        body = resp.json()
        return body.get("error", resp.text)
    except Exception:
        return resp.text or f"HTTP {resp.status_code}"


async def start_bot(user_id: int) -> dict:
    """Start (or re-start) the OpenClaw gateway for a user."""
    async with _client() as client:
        resp = await client.post(f"/instances/{user_id}/start")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor start_bot failed for user {user_id}: {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def stop_bot(user_id: int) -> dict:
    """Stop the OpenClaw gateway for a user."""
    async with _client() as client:
        resp = await client.post(f"/instances/{user_id}/stop")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor stop_bot failed for user {user_id}: {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def get_bot_status(user_id: int) -> dict:
    """Get the status + health of a user's OpenClaw gateway."""
    async with _client() as client:
        resp = await client.get(f"/instances/{user_id}/status")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor get_bot_status failed for user {user_id}: {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def delete_bot(user_id: int) -> dict:
    """Stop and delete all state for a user's OpenClaw gateway."""
    async with _client() as client:
        resp = await client.delete(f"/instances/{user_id}")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor delete_bot failed for user {user_id}: {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def list_bots() -> dict:
    """List all running OpenClaw instances (admin)."""
    async with _client() as client:
        resp = await client.get("/instances")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor list_bots failed: {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def proxy_to_bot(user_id: int, path: str, method: str = "GET", body: dict | None = None) -> dict:
    """Proxy an HTTP request to a user's OpenClaw gateway."""
    async with _client() as client:
        url = f"/instances/{user_id}/proxy/{path.lstrip('/')}"
        resp = await client.request(method, url, json=body if body else None, timeout=60.0)
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor proxy_to_bot failed for user {user_id} ({method} {path}): {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}


async def proxy_to_bot_raw(
    user_id: int,
    path: str,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Proxy an HTTP request to a user's OpenClaw gateway and return the raw response.

    Returns ``(status_code, headers_dict, body_bytes)`` so the caller can
    build a streaming/binary response (e.g. serving Control UI assets).
    """
    async with _client() as client:
        url = f"/instances/{user_id}/proxy/{path.lstrip('/')}"
        req_headers = dict(headers or {})
        # Remove hop-by-hop headers that httpx would reject
        for h in ("host", "transfer-encoding", "connection"):
            req_headers.pop(h, None)
        resp = await client.request(
            method,
            url,
            content=body,
            headers=req_headers,
            timeout=60.0,
        )
        # Build a plain dict of response headers
        resp_headers: dict[str, str] = {}
        for key, value in resp.headers.multi_items():
            lower = key.lower()
            # Strip framing/hop-by-hop headers that would block iframe embedding
            if lower in (
                "x-frame-options",
                "content-security-policy",
                "transfer-encoding",
                "connection",
                "content-encoding",
                "content-length",
            ):
                continue
            resp_headers[key] = value
        return resp.status_code, resp_headers, resp.content


async def get_supervisor_health() -> dict:
    """Check the supervisor health."""
    async with _client() as client:
        resp = await client.get("/health")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def get_bot_logs(user_id: int) -> list[dict]:
    """Fetch buffered log entries for a user's OpenClaw gateway."""
    async with _client() as client:
        resp = await client.get(f"/instances/{user_id}/logs")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        data = resp.json()
        return data.get("entries", [])


async def stream_bot_logs(user_id: int) -> AsyncIterator[str]:
    """Stream real-time log lines for a user's OpenClaw gateway via SSE.

    Yields raw SSE chunks (``data: ...\\n\\n``) that are forwarded
    verbatim to the client through a ``StreamingResponse``.
    """
    async with _client() as client:
        async with client.stream(
            "GET",
            f"/instances/{user_id}/logs/stream",
            timeout=None,  # keep-alive, no read timeout
        ) as resp:
            if resp.status_code >= 400:
                await resp.aread()
                detail = _extract_error(resp)
                raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
            async for line in resp.aiter_lines():
                yield line + "\n"


def get_supervisor_ws_url(user_id: int) -> str:
    """
    Return the internal WebSocket URL for proxying to a user's gateway.
    Used by the WS proxy controller to connect to the supervisor.
    """
    base = SUPERVISOR_URL.replace("http://", "ws://").replace("https://", "wss://")
    return f"{base}/instances/{user_id}/proxy/ws"


# ── Config Provisioning ────────────────────────────────────────────────────────


def _build_openclaw_config(channels: dict[str, Any]) -> dict:
    """Build an openclaw.json config object from the user's channel settings.

    The returned dict is written to the user's state dir so the gateway
    process picks up channel tokens on startup or config reload.
    """
    config: dict[str, Any] = {"channels": {}}

    # Telegram
    tg = channels.get("telegram")
    if tg:
        tg_cfg: dict[str, Any] = {}
        if tg.get("mode") == "own" and tg.get("botToken"):
            tg_cfg["botToken"] = tg["botToken"]
        # For shared mode the gateway doesn't run its own bot —
        # messages are proxied from the shared webhook controller.
        # We still mark the channel as enabled for status display.
        if tg.get("mode") == "shared":
            tg_cfg["_sharedMode"] = True
            # Auto-registered users: set dmPolicy to "open" so their messages
            # aren't blocked by pairing.
            tg_cfg["dmPolicy"] = "open"
            if tg.get("chatId"):
                tg_cfg["allowFrom"] = [str(tg["chatId"])]
        if tg_cfg:
            config["channels"]["telegram"] = tg_cfg

    # Discord
    dc = channels.get("discord")
    if dc:
        dc_cfg: dict[str, Any] = {}
        if dc.get("botToken"):
            dc_cfg["botToken"] = dc["botToken"]
        if dc.get("mode") == "shared":
            dc_cfg["_sharedMode"] = True
            dc_cfg["dmPolicy"] = "open"
            if dc.get("channelUserId"):
                dc_cfg["allowFrom"] = [dc["channelUserId"]]
        if dc_cfg:
            config["channels"]["discord"] = dc_cfg

    # Slack
    sl = channels.get("slack")
    if sl:
        slack_cfg: dict[str, Any] = {}
        if sl.get("botToken"):
            slack_cfg["botToken"] = sl["botToken"]
        if sl.get("signingSecret"):
            slack_cfg["signingSecret"] = sl["signingSecret"]
        if sl.get("appToken"):
            slack_cfg["appToken"] = sl["appToken"]
        if sl.get("mode") == "shared":
            slack_cfg["_sharedMode"] = True
            slack_cfg["dmPolicy"] = "open"
            if sl.get("channelUserId"):
                slack_cfg["allowFrom"] = [sl["channelUserId"]]
        if slack_cfg:
            config["channels"]["slack"] = slack_cfg

    # WhatsApp
    wa = channels.get("whatsapp")
    if wa:
        wa_cfg: dict[str, Any] = {}
        if wa.get("enabled"):
            wa_cfg["_enabled"] = True
        if wa.get("mode") == "shared":
            wa_cfg["_sharedMode"] = True
            wa_cfg["dmPolicy"] = "open"
            if wa.get("channelUserId"):
                wa_cfg["allowFrom"] = [wa["channelUserId"]]
        if wa_cfg:
            config["channels"]["whatsapp"] = wa_cfg

    # LINE
    li = channels.get("line")
    if li:
        li_cfg: dict[str, Any] = {}
        if li.get("mode") == "shared":
            li_cfg["_sharedMode"] = True
            li_cfg["dmPolicy"] = "open"
            if li.get("channelUserId"):
                li_cfg["allowFrom"] = [li["channelUserId"]]
        if li_cfg:
            config["channels"]["line"] = li_cfg

    # Feishu
    fs = channels.get("feishu")
    if fs:
        fs_cfg: dict[str, Any] = {}
        if fs.get("mode") == "shared":
            fs_cfg["_sharedMode"] = True
            fs_cfg["dmPolicy"] = "open"
            if fs.get("channelUserId"):
                fs_cfg["allowFrom"] = [fs["channelUserId"]]
        if fs_cfg:
            config["channels"]["feishu"] = fs_cfg

    # Generic shared-mode channels (signal, irc, matrix, msteams, googlechat, etc.)
    for ch_name in ("signal", "irc", "matrix", "msteams", "googlechat"):
        ch = channels.get(ch_name)
        if ch:
            ch_cfg: dict[str, Any] = {}
            if ch.get("mode") == "shared":
                ch_cfg["_sharedMode"] = True
                ch_cfg["dmPolicy"] = "open"
                if ch.get("channelUserId"):
                    ch_cfg["allowFrom"] = [ch["channelUserId"]]
            if ch_cfg:
                config["channels"][ch_name] = ch_cfg

    # Web Chat — always available when gateway is running, no config needed.

    # Strip internal-only keys (prefixed with "_") that are not part of the
    # OpenClaw config schema.  The schema uses strict validation and will
    # reject any unrecognised keys like "_enabled" or "_sharedMode".
    for ch_cfg in config.get("channels", {}).values():
        for key in [k for k in ch_cfg if k.startswith("_")]:
            del ch_cfg[key]

    # Remove empty channel sections that had only internal keys.
    # Note: shared-mode channels keep at least "dmPolicy" so they won't
    # be empty after stripping "_"-prefixed keys.
    config["channels"] = {
        k: v for k, v in config["channels"].items() if v
    }

    return config


async def write_user_config(user_id: int, channels: dict[str, Any]) -> dict:
    """Write openclaw.json into the user's supervisor state dir.

    This calls the supervisor's ``PUT /instances/:userId/config`` endpoint
    which writes the file on disk even if the instance is not running.
    """
    config = _build_openclaw_config(channels)
    async with _client() as client:
        resp = await client.put(
            f"/instances/{user_id}/config",
            json=config,
        )
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor push_user_config failed for user {user_id}: {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def reload_user_config(user_id: int) -> dict:
    """Signal a running gateway to reload its config file.

    Calls ``POST /instances/:userId/reload-config``.  If the instance
    is not running this is a no-op on the supervisor side.
    """
    async with _client() as client:
        resp = await client.post(f"/instances/{user_id}/reload-config")
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            logger.error(f"Supervisor reload_user_config failed for user {user_id}: {resp.status_code} — {detail}")
            raise RuntimeError(f"Supervisor error ({resp.status_code}): {detail}")
        return resp.json()


async def ensure_bot_running(user_id: int, channels: dict[str, Any] | None = None) -> dict:
    """Write config (if provided) and ensure the gateway is running.

    Used both by the channel-connect flow and the login auto-start.
    Returns the instance status dict.
    """
    if channels:
        await write_user_config(user_id, channels)

    # Check current status first to decide start vs reload
    try:
        status = await get_bot_status(user_id)
        if status.get("status") == "running":
            # Already running — reload config if we wrote one
            if channels:
                await reload_user_config(user_id)
            return status
    except Exception:
        pass  # supervisor may be unreachable or instance doesn't exist

    # Start the gateway (supervisor handles "already running" gracefully)
    return await start_bot(user_id)


async def ensure_bot_running_fire_and_forget(user_id: int, channels: dict[str, Any] | None = None) -> None:
    """Fire-and-forget wrapper — logs errors but never raises."""
    try:
        await ensure_bot_running(user_id, channels)
    except Exception as e:
        logger.warning(
            "Failed to auto-start OpenClaw for user %s: %s",
            user_id,
            e,
        )


async def start_all_configured_bots() -> dict:
    """Start OpenClaw gateways for ALL users with configured bot_channels.

    Called once on server startup to restore gateways after a deploy/restart.
    Runs fire-and-forget for each user — errors are logged but never raised.
    Returns summary dict with counts.
    """
    from sqlmodel import select

    from app.component.database import session_make
    from app.model.user.user import User

    s = session_make()
    try:
        users = s.exec(
            select(User).where(User.bot_channels.isnot(None))
        ).all()
    finally:
        s.close()

    started, failed = 0, 0
    for user in users:
        try:
            await ensure_bot_running(user.id, user.bot_channels)
            started += 1
            logger.info("Auto-started OpenClaw gateway for user %s", user.id)
        except Exception as e:
            failed += 1
            logger.warning(
                "Failed to auto-start OpenClaw for user %s: %s", user.id, e
            )

    summary = {"total": len(users), "started": started, "failed": failed}
    logger.info("OpenClaw auto-start complete: %s", summary)
    return summary
