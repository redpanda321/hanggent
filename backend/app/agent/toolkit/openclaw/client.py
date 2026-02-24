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
Hybrid WS + HTTP async client for the OpenClaw messaging gateway.

OpenClaw exposes two protocols:
- **HTTP REST**: ``/v1/chat/completions``, ``/v1/responses``,
  ``/tools/invoke`` (OpenAI-compatible endpoints)
- **WebSocket RPC**: JSON frames with ``{type, id, method, params}`` for
  real-time gateway control (channels, sessions, send, chat, agent, cron,
  health, config, etc.)

This client wraps both protocols into a single ergonomic interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)


class OpenClawClient:
    """Hybrid WS + HTTP async client for the OpenClaw gateway."""

    def __init__(
        self,
        base_url: str | None = None,
        auth_token: str | None = None,
        timeout: float = 300.0,
    ):
        self._base_url = (
            base_url
            or os.getenv("OPENCLAW_URL")
            or "http://localhost:18789"
        )
        self._ws_url = self._base_url.replace(
            "http://", "ws://"
        ).replace("https://", "wss://")
        self._auth_token = auth_token or os.getenv(
            "OPENCLAW_AUTH_TOKEN", ""
        )
        self._timeout = timeout

        # HTTP client (lazy init)
        self._http: httpx.AsyncClient | None = None

        # WS state
        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._ws_lock = asyncio.Lock()
        self._ws_counter = 0
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._event_listeners: list[asyncio.Queue[dict[str, Any]]] = []
        self._reader_task: asyncio.Task | None = None

    # ==================================================================
    # HTTP layer
    # ==================================================================

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            headers: dict[str, str] = {
                "Content-Type": "application/json",
            }
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout,
            )
        return self._http

    async def health_http(self) -> bool:
        """Quick HTTP health check."""
        try:
            client = await self._get_http()
            resp = await client.get("/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def chat_completions(
        self,
        messages: list[dict[str, Any]],
        model: str = "default",
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncGenerator[str, None]:
        """POST /v1/chat/completions (OpenAI-compatible).

        When *stream* is False returns the full response dict.
        When *stream* is True returns an async generator of SSE data lines.
        """
        client = await self._get_http()
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }
        if stream:
            return self._stream_chat(client, body)
        resp = await client.post("/v1/chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()

    async def _stream_chat(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json=body,
            timeout=self._timeout,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if line.startswith("data:"):
                    yield line[5:].strip()

    async def responses_create(
        self,
        input_data: str | list[dict[str, Any]],
        model: str = "default",
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """POST /v1/responses — OpenResponses API."""
        client = await self._get_http()
        body: dict[str, Any] = {
            "model": model,
            "input": input_data,
            **kwargs,
        }
        if tools:
            body["tools"] = tools
        resp = await client.post("/v1/responses", json=body)
        resp.raise_for_status()
        return resp.json()

    async def invoke_tool(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        session_key: str = "main",
    ) -> dict[str, Any]:
        """POST /tools/invoke — invoke a tool directly."""
        client = await self._get_http()
        body: dict[str, Any] = {
            "tool": tool,
            "args": args or {},
            "sessionKey": session_key,
        }
        resp = await client.post("/tools/invoke", json=body)
        resp.raise_for_status()
        return resp.json()

    # ==================================================================
    # WebSocket layer
    # ==================================================================

    async def _ensure_ws(self) -> Any:
        """Ensure a WS connection is established and handshake complete."""
        async with self._ws_lock:
            if self._ws is not None:
                return self._ws
            try:
                import websockets
            except ImportError:
                raise RuntimeError(
                    "websockets package required: "
                    "pip install websockets>=13.0"
                )

            extra_headers = {}
            if self._auth_token:
                extra_headers["Authorization"] = (
                    f"Bearer {self._auth_token}"
                )

            self._ws = await websockets.connect(
                self._ws_url,
                additional_headers=extra_headers,
                max_size=10 * 1024 * 1024,  # 10 MB
            )

            # Start background reader
            self._reader_task = asyncio.create_task(
                self._ws_reader(), name="openclaw-ws-reader"
            )

            # Perform connect handshake
            await self._ws_call("connect", {})

            return self._ws

    async def _ws_reader(self) -> None:
        """Background task that reads WS frames and dispatches."""
        try:
            async for raw in self._ws:
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    logger.debug(
                        "OpenClaw WS: non-JSON frame: %s", raw[:200]
                    )
                    continue

                frame_type = frame.get("type")

                if frame_type == "res":
                    # Response to a call
                    req_id = frame.get("id")
                    future = self._pending.pop(req_id, None)
                    if future and not future.done():
                        future.set_result(frame)
                elif frame_type == "event":
                    # Push event to all listeners
                    for q in self._event_listeners:
                        try:
                            q.put_nowait(frame)
                        except asyncio.QueueFull:
                            pass
                elif frame_type == "push":
                    # Pushed data (chat deltas, etc.)
                    for q in self._event_listeners:
                        try:
                            q.put_nowait(frame)
                        except asyncio.QueueFull:
                            pass
                else:
                    logger.debug(
                        "OpenClaw WS: unknown frame type: %s",
                        frame_type,
                    )
        except Exception as e:
            logger.info("OpenClaw WS reader stopped: %s", e)
        finally:
            # Clean up pending futures
            for future in self._pending.values():
                if not future.done():
                    future.cancel()
            self._pending.clear()

    async def _ws_call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a WS RPC request and wait for the response."""
        await self._ensure_ws()

        self._ws_counter += 1
        req_id = str(self._ws_counter)
        frame = {
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[req_id] = future

        await self._ws.send(json.dumps(frame))

        try:
            result = await asyncio.wait_for(
                future, timeout=timeout or self._timeout
            )
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(
                f"OpenClaw WS call '{method}' timed out"
            )

        if not result.get("ok", False):
            error = result.get("error", result.get("payload", {}))
            raise RuntimeError(
                f"OpenClaw WS call '{method}' failed: {error}"
            )

        return result.get("payload", {})

    def subscribe_events(self) -> asyncio.Queue[dict[str, Any]]:
        """Create a new event subscription queue.

        Returns an ``asyncio.Queue`` that receives all WS push events
        and event frames. Call ``unsubscribe_events()`` when done.
        """
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._event_listeners.append(q)
        return q

    def unsubscribe_events(
        self, q: asyncio.Queue[dict[str, Any]]
    ) -> None:
        """Remove an event subscription queue."""
        try:
            self._event_listeners.remove(q)
        except ValueError:
            pass

    # ==================================================================
    # WS RPC convenience methods
    # ==================================================================

    async def health(self) -> dict[str, Any]:
        """WS health check."""
        return await self._ws_call("health")

    async def channels_status(self) -> list[dict[str, Any]]:
        """Get status of all configured channels."""
        return await self._ws_call("channels.status")

    async def sessions_list(self) -> list[dict[str, Any]]:
        """List all sessions."""
        return await self._ws_call("sessions.list")

    async def sessions_preview(
        self, session_key: str
    ) -> dict[str, Any]:
        """Get a preview of a session's messages."""
        return await self._ws_call(
            "sessions.preview", {"sessionKey": session_key}
        )

    async def sessions_reset(self, session_key: str) -> dict[str, Any]:
        """Reset a session's history."""
        return await self._ws_call(
            "sessions.reset", {"sessionKey": session_key}
        )

    async def sessions_delete(
        self, session_key: str
    ) -> dict[str, Any]:
        """Delete a session."""
        return await self._ws_call(
            "sessions.delete", {"sessionKey": session_key}
        )

    async def send_message(
        self,
        to: str,
        message: str,
        channel: str | None = None,
        media_url: str | None = None,
    ) -> dict[str, Any]:
        """Send an outbound message through a channel."""
        params: dict[str, Any] = {"to": to, "message": message}
        if channel:
            params["channel"] = channel
        if media_url:
            params["mediaUrl"] = media_url
        return await self._ws_call("send", params)

    async def chat_send(
        self,
        session_key: str,
        message: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Send a chat message within a session."""
        return await self._ws_call(
            "chat.send",
            {
                "sessionKey": session_key,
                "message": message,
                "idempotencyKey": idempotency_key
                or str(uuid.uuid4()),
            },
        )

    async def chat_abort(self, run_id: str) -> dict[str, Any]:
        """Abort an active chat run."""
        return await self._ws_call("chat.abort", {"runId": run_id})

    async def chat_history(
        self, session_key: str
    ) -> dict[str, Any]:
        """Get chat history for a session."""
        return await self._ws_call(
            "chat.history", {"sessionKey": session_key}
        )

    async def agent_invoke(
        self,
        session_key: str,
        message: str | None = None,
        extra_system_prompt: str | None = None,
        lane: str | None = None,
        label: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Invoke the AI agent on a session."""
        params: dict[str, Any] = {"sessionKey": session_key}
        if message:
            params["message"] = message
        if extra_system_prompt:
            params["extraSystemPrompt"] = extra_system_prompt
        if lane:
            params["lane"] = lane
        if label:
            params["label"] = label
        return await self._ws_call(
            "agent", params, timeout=timeout or 600.0
        )

    async def agent_wait(
        self,
        run_id: str,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Wait for an agent run to complete."""
        return await self._ws_call(
            "agent.wait",
            {"runId": run_id},
            timeout=timeout or 600.0,
        )

    async def models_list(self) -> list[dict[str, Any]]:
        """List available models."""
        return await self._ws_call("models.list")

    async def config_get(self) -> dict[str, Any]:
        """Get current gateway configuration."""
        return await self._ws_call("config.get")

    async def config_set(
        self,
        config: dict[str, Any],
        base_hash: str | None = None,
    ) -> dict[str, Any]:
        """Set gateway configuration with optional optimistic
        concurrency."""
        params: dict[str, Any] = {"config": config}
        if base_hash:
            params["baseHash"] = base_hash
        return await self._ws_call("config.set", params)

    async def cron_list(self) -> list[dict[str, Any]]:
        """List all scheduled cron tasks."""
        return await self._ws_call("cron.list")

    async def cron_add(
        self,
        schedule: str,
        action: dict[str, Any],
        label: str | None = None,
    ) -> dict[str, Any]:
        """Add a new cron task."""
        params: dict[str, Any] = {
            "schedule": schedule,
            "action": action,
        }
        if label:
            params["label"] = label
        return await self._ws_call("cron.add", params)

    async def cron_remove(self, cron_id: str) -> dict[str, Any]:
        """Remove a cron task."""
        return await self._ws_call(
            "cron.remove", {"id": cron_id}
        )

    async def nodes_list(self) -> list[dict[str, Any]]:
        """List connected nodes in the mesh."""
        return await self._ws_call("nodes.list")

    async def tts_speak(
        self, text: str, voice: str | None = None
    ) -> dict[str, Any]:
        """Trigger text-to-speech."""
        params: dict[str, Any] = {"text": text}
        if voice:
            params["voice"] = voice
        return await self._ws_call("tts.speak", params)

    async def exec_approval(
        self,
        approval_id: str,
        approved: bool,
    ) -> dict[str, Any]:
        """Respond to an execution approval request."""
        return await self._ws_call(
            "exec.approval.respond",
            {"id": approval_id, "approved": approved},
        )

    # ==================================================================
    # Lifecycle
    # ==================================================================

    async def close(self) -> None:
        """Close all connections."""
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._http:
            await self._http.aclose()
            self._http = None

        self._event_listeners.clear()
        self._pending.clear()
