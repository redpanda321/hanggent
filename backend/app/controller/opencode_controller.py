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
Proxy controller for OpenCode server.
Provides endpoints for the frontend to interact with the OpenCode service
without needing direct access to the OpenCode server port.
"""

import logging
import os
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("opencode_controller")

router = APIRouter(prefix="/opencode", tags=["OpenCode"])

OPENCODE_BASE_URL = os.getenv("OPENCODE_BASE_URL", "http://localhost:4096")

# Shared httpx client for connection pooling
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=OPENCODE_BASE_URL, timeout=30.0
        )
    return _client


class OpenCodeHealthResponse(BaseModel):
    status: str
    opencode_available: bool
    base_url: str


class SessionCreateRequest(BaseModel):
    system_prompt: Optional[str] = None


class MessageRequest(BaseModel):
    content: str


@router.get("/health", response_model=OpenCodeHealthResponse)
async def opencode_health():
    """Check if the OpenCode server is reachable."""
    try:
        client = _get_client()
        resp = await client.get("/session")
        available = resp.status_code == 200
    except Exception:
        available = False

    return OpenCodeHealthResponse(
        status="ok" if available else "unavailable",
        opencode_available=available,
        base_url=OPENCODE_BASE_URL,
    )


@router.get("/session")
async def list_sessions() -> Any:
    """List all OpenCode sessions."""
    try:
        client = _get_client()
        resp = await client.get("/session")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.post("/session")
async def create_session(req: Optional[SessionCreateRequest] = None) -> Any:
    """Create a new OpenCode session."""
    try:
        client = _get_client()
        body = {}
        if req and req.system_prompt:
            body["system_prompt"] = req.system_prompt
        resp = await client.post("/session", json=body)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.get("/session/{session_id}")
async def get_session(session_id: str) -> Any:
    """Get a specific OpenCode session."""
    try:
        client = _get_client()
        resp = await client.get(f"/session/{session_id}")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.get("/session/{session_id}/messages")
async def get_session_messages(session_id: str) -> Any:
    """Get messages for an OpenCode session."""
    try:
        client = _get_client()
        resp = await client.get(f"/session/{session_id}/messages")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.post("/session/{session_id}/message")
async def send_message(session_id: str, req: MessageRequest) -> Any:
    """Send a message to an OpenCode session (streaming response)."""
    try:
        client = _get_client()

        async def stream_response():
            async with client.stream(
                "POST",
                f"/session/{session_id}/message",
                json={"content": req.content},
                timeout=120.0,
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

        return StreamingResponse(
            stream_response(), media_type="text/event-stream"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.post("/session/{session_id}/abort")
async def abort_session(session_id: str) -> Any:
    """Abort an active OpenCode session."""
    try:
        client = _get_client()
        resp = await client.post(f"/session/{session_id}/abort")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.get("/session/{session_id}/diff")
async def get_session_diff(session_id: str) -> Any:
    """Get file diff for an OpenCode session."""
    try:
        client = _get_client()
        resp = await client.get(f"/session/{session_id}/diff")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.get("/event")
async def stream_events(
    session_id: Optional[str] = Query(None),
) -> StreamingResponse:
    """Proxy SSE events from OpenCode server."""
    try:
        client = _get_client()
        params = {}
        if session_id:
            params["sessionID"] = session_id

        async def event_stream():
            async with client.stream(
                "GET", "/event", params=params, timeout=None
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    yield f"{line}\n"

        return StreamingResponse(
            event_stream(), media_type="text/event-stream"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )


@router.get("/provider")
async def list_providers() -> Any:
    """List available OpenCode providers."""
    try:
        client = _get_client()
        resp = await client.get("/provider")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenCode error: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="OpenCode server is not available",
        )
