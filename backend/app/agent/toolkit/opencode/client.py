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
Async HTTP client for the OpenCode server API.

Communicates with the opencode server (default http://localhost:4096)
to manage sessions, send prompts, stream events, and configure providers.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

# Map hanggent model_platform values to opencode providerIDs
PLATFORM_TO_PROVIDER: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "groq": "groq",
    "deepseek": "deepseek",
    "mistral": "mistral",
    "xai": "xai",
    "openai-compatible": "custom",
    "openai-compatible-model": "custom",
    "litellm": "custom",
    "openrouter": "openrouter",
    "azure": "azure",
}


class OpenCodeClient:
    """Async HTTP client for the OpenCode server REST + SSE API."""

    def __init__(
        self,
        base_url: str | None = None,
        password: str | None = None,
        timeout: float = 300.0,
    ):
        self._base_url = base_url or os.getenv(
            "OPENCODE_URL", "http://localhost:4096"
        )
        self._password = password or os.getenv("OPENCODE_SERVER_PASSWORD")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._password:
                import base64

                creds = base64.b64encode(
                    f"user:{self._password}".encode()
                ).decode()
                headers["Authorization"] = f"Basic {creds}"

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> bool:
        """Check if the opencode server is reachable and healthy."""
        try:
            client = await self._get_client()
            resp = await client.get("/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def create_session(
        self,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Create a new opencode session."""
        client = await self._get_client()
        body: dict[str, Any] = {}
        if title:
            body["title"] = title
        resp = await client.post("/session", json=body)
        resp.raise_for_status()
        return resp.json()

    async def get_session(self, session_id: str) -> dict[str, Any]:
        client = await self._get_client()
        resp = await client.get(f"/session/{session_id}")
        resp.raise_for_status()
        return resp.json()

    async def list_sessions(
        self,
        limit: int | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        client = await self._get_client()
        params: dict[str, Any] = {}
        if limit:
            params["limit"] = limit
        if search:
            params["search"] = search
        resp = await client.get("/session", params=params)
        resp.raise_for_status()
        return resp.json()

    async def delete_session(self, session_id: str) -> None:
        client = await self._get_client()
        resp = await client.delete(f"/session/{session_id}")
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Messages / Prompts
    # ------------------------------------------------------------------

    async def send_message(
        self,
        session_id: str,
        text: str,
        provider_id: str | None = None,
        model_id: str | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Send a message and wait for the full response (blocking stream)."""
        client = await self._get_client()
        body: dict[str, Any] = {
            "parts": [{"type": "text", "text": text}],
        }
        if provider_id and model_id:
            body["model"] = {
                "providerID": provider_id,
                "modelID": model_id,
            }
        if system:
            body["system"] = system

        # The endpoint streams but returns final JSON when complete
        async with client.stream(
            "POST",
            f"/session/{session_id}/message",
            json=body,
            timeout=self._timeout,
        ) as resp:
            resp.raise_for_status()
            content = await resp.aread()
            return json.loads(content)

    async def send_message_async(
        self,
        session_id: str,
        text: str,
        provider_id: str | None = None,
        model_id: str | None = None,
        system: str | None = None,
    ) -> None:
        """Fire-and-forget message. Returns immediately (204)."""
        client = await self._get_client()
        body: dict[str, Any] = {
            "parts": [{"type": "text", "text": text}],
        }
        if provider_id and model_id:
            body["model"] = {
                "providerID": provider_id,
                "modelID": model_id,
            }
        if system:
            body["system"] = system

        resp = await client.post(
            f"/session/{session_id}/prompt_async", json=body
        )
        resp.raise_for_status()

    async def abort_session(self, session_id: str) -> None:
        """Abort active processing in a session."""
        client = await self._get_client()
        resp = await client.post(f"/session/{session_id}/abort")
        resp.raise_for_status()

    async def get_messages(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        """Get all messages (with parts) for a session."""
        client = await self._get_client()
        resp = await client.get(f"/session/{session_id}/message")
        resp.raise_for_status()
        return resp.json()

    async def get_diff(self, session_id: str) -> dict[str, Any]:
        """Get file diffs for a session."""
        client = await self._get_client()
        resp = await client.get(f"/session/{session_id}/diff")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Auth / Provider configuration
    # ------------------------------------------------------------------

    async def set_provider_auth(
        self,
        provider_id: str,
        api_key: str,
    ) -> None:
        """Set API key credentials for a provider."""
        client = await self._get_client()
        resp = await client.put(
            f"/auth/{provider_id}",
            json={"type": "api", "key": api_key},
        )
        resp.raise_for_status()

    async def list_providers(self) -> dict[str, Any]:
        """List all providers with models and connection status."""
        client = await self._get_client()
        resp = await client.get("/provider")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Agents / Skills
    # ------------------------------------------------------------------

    async def list_agents(self) -> list[dict[str, Any]]:
        client = await self._get_client()
        resp = await client.get("/agent")
        resp.raise_for_status()
        return resp.json()

    async def list_skills(self) -> list[dict[str, Any]]:
        client = await self._get_client()
        resp = await client.get("/skill")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # SSE Event Stream
    # ------------------------------------------------------------------

    async def stream_events(self) -> AsyncGenerator[dict[str, Any], None]:
        """
        Connect to opencode's global SSE event stream (``GET /event``).

        Yields parsed JSON payloads:
        ``{"directory": "...", "payload": {"type": "...", "properties": {...}}}``
        """
        client = await self._get_client()
        try:
            async with client.stream(
                "GET", "/event", timeout=None
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if not data_str:
                        continue
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.debug(
                            "Failed to parse SSE data: %s", data_str[:200]
                        )
        except httpx.RemoteProtocolError:
            logger.info("OpenCode SSE stream disconnected")
        except Exception as e:
            logger.error("OpenCode SSE stream error: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def map_provider(
        model_platform: str,
        model_type: str,
        api_key: str | None = None,
        api_url: str | None = None,
    ) -> tuple[str, str]:
        """
        Map hanggent's ``model_platform``/``model_type`` to opencode's
        ``providerID``/``modelID``.

        Returns (provider_id, model_id).
        """
        platform_lower = (model_platform or "").lower()
        provider_id = PLATFORM_TO_PROVIDER.get(platform_lower, "custom")
        model_id = model_type or ""
        return provider_id, model_id
