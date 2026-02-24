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
Proxy controller for the OpenClaw messaging gateway.

Provides HTTP endpoints for the frontend to interact with the OpenClaw
gateway without needing direct access. Also serves the OpenClaw Control UI
in an iframe-safe manner by stripping frame-blocking headers.
"""

import logging
import os
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("openclaw_controller")

router = APIRouter(prefix="/openclaw", tags=["OpenClaw"])

OPENCLAW_BASE_URL = os.getenv("OPENCLAW_URL", "http://localhost:18789")
OPENCLAW_AUTH_TOKEN = os.getenv("OPENCLAW_AUTH_TOKEN", "")

# Shared httpx client for connection pooling
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if OPENCLAW_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {OPENCLAW_AUTH_TOKEN}"
        _client = httpx.AsyncClient(
            base_url=OPENCLAW_BASE_URL,
            headers=headers,
            timeout=30.0,
        )
    return _client


# ==================================================================
# Response models
# ==================================================================


class OpenClawHealthResponse(BaseModel):
    status: str
    openclaw_available: bool
    base_url: str


class SendMessageRequest(BaseModel):
    to: str
    message: str
    channel: Optional[str] = None
    media_url: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_key: str = "main"


class CronRequest(BaseModel):
    schedule: str
    action_type: str
    action_params: dict[str, Any] = {}
    label: Optional[str] = None


class ToolInvokeRequest(BaseModel):
    tool: str
    args: dict[str, Any] = {}
    session_key: str = "main"


# ==================================================================
# Health
# ==================================================================


@router.get("/health", response_model=OpenClawHealthResponse)
async def openclaw_health():
    """Check if the OpenClaw gateway is reachable."""
    try:
        client = _get_client()
        resp = await client.get("/health", timeout=5.0)
        available = resp.status_code == 200
    except Exception:
        available = False

    return OpenClawHealthResponse(
        status="ok" if available else "unavailable",
        openclaw_available=available,
        base_url=OPENCLAW_BASE_URL,
    )


# ==================================================================
# Chat completions proxy
# ==================================================================


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy OpenAI-compatible chat completions to OpenClaw."""
    body = await request.json()
    client = _get_client()

    stream = body.get("stream", False)
    if stream:

        async def _stream():
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json=body,
                timeout=300.0,
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        resp = await client.post(
            "/v1/chat/completions", json=body, timeout=300.0
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenClaw error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not available",
        )


# ==================================================================
# Channels
# ==================================================================


@router.get("/channels")
async def channels_status():
    """Get status of all connected channels."""
    try:
        client = _get_client()
        # Try HTTP health endpoint — channel status may be
        # available via a REST endpoint depending on gateway version.
        # Fall back to a simple proxy.
        resp = await client.get("/channels", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenClaw error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not available",
        )


# ==================================================================
# Sessions
# ==================================================================


@router.get("/sessions")
async def list_sessions():
    """List all active gateway sessions."""
    try:
        client = _get_client()
        resp = await client.get("/sessions", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenClaw error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not available",
        )


# ==================================================================
# Models
# ==================================================================


@router.get("/models")
async def list_models():
    """List available models on the gateway."""
    try:
        client = _get_client()
        resp = await client.get("/v1/models", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenClaw error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not available",
        )


# ==================================================================
# Send message
# ==================================================================


@router.post("/send")
async def send_message(req: SendMessageRequest):
    """Send an outbound message through the gateway.

    Note: This goes through the HTTP layer. For real-time WS-based
    sending, the agent toolkit uses the WS client directly.
    """
    try:
        client = _get_client()
        body: dict[str, Any] = {
            "to": req.to,
            "message": req.message,
        }
        if req.channel:
            body["channel"] = req.channel
        if req.media_url:
            body["mediaUrl"] = req.media_url

        resp = await client.post("/send", json=body, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenClaw error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not available",
        )


# ==================================================================
# Tool invocation
# ==================================================================


@router.post("/tools/invoke")
async def invoke_tool(req: ToolInvokeRequest):
    """Invoke a tool on the gateway."""
    try:
        client = _get_client()
        body: dict[str, Any] = {
            "tool": req.tool,
            "args": req.args,
            "sessionKey": req.session_key,
        }
        resp = await client.post(
            "/tools/invoke", json=body, timeout=60.0
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenClaw error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not available",
        )


# ==================================================================
# Control UI proxy (iframe-safe)
# ==================================================================

# OpenClaw serves its Control UI at the root path by default and sets
# X-Frame-Options: DENY.  We proxy the UI here, stripping the
# frame-blocking headers so it can be embedded in an iframe.

_FRAME_STRIP_HEADERS = {
    "x-frame-options",
    "content-security-policy",
}


@router.get("/ui/{path:path}")
async def proxy_control_ui(path: str, request: Request):
    """Proxy the OpenClaw Control UI, stripping frame-blocking headers."""
    target_url = f"/{path}" if path else "/"

    # Forward query params
    if request.query_params:
        target_url += f"?{request.query_params}"

    try:
        client = _get_client()
        resp = await client.get(target_url, timeout=15.0)

        # Strip frame-blocking headers
        headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower() not in _FRAME_STRIP_HEADERS
        }

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not available",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Error proxying Control UI: {e}",
        )
