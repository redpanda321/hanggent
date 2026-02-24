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
OpenCodeToolkit — CAMEL-compatible toolkit that bridges hanggent's workforce
agent system to the OpenCode coding agent server.

Exposes high-level tools (``opencode_execute``, ``opencode_message``,
``opencode_abort``, ``opencode_diff``) that the agent LLM can call.
Under the hood it manages opencode sessions, streams events via
``OpenCodeEventBridge``, and translates them to hanggent SSE actions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from camel.toolkits import BaseToolkit, FunctionTool

from app.agent.toolkit.abstract_toolkit import AbstractToolkit
from app.agent.toolkit.opencode.client import OpenCodeClient
from app.agent.toolkit.opencode.event_bridge import OpenCodeEventBridge
from app.service.task import Agents, TaskLock

logger = logging.getLogger(__name__)

# Maximum time (seconds) to wait for an opencode session to go idle.
_IDLE_TIMEOUT = 600.0


class OpenCodeToolkit(BaseToolkit, AbstractToolkit):
    """Toolkit that delegates coding tasks to an OpenCode server session."""

    agent_name: str = Agents.opencode_agent  # type: ignore[assignment]

    def __init__(
        self,
        api_task_id: str,
        agent_name: str | None = None,
        opencode_url: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
        working_directory: str | None = None,
    ):
        super().__init__()

        self.api_task_id = api_task_id
        if agent_name is not None:
            self.agent_name = agent_name

        self._client = OpenCodeClient(base_url=opencode_url)
        self._provider_id = provider_id
        self._model_id = model_id
        self._api_key = api_key
        self._api_url = api_url
        self._working_directory = working_directory

        # Active session state
        self._session_id: str | None = None
        self._bridge: OpenCodeEventBridge | None = None
        self._agent_id: str = str(uuid.uuid4())[:8]
        self._process_task_id: str = ""
        self._auth_configured: bool = False

    # ------------------------------------------------------------------
    # Auth helper — configure provider key on first use
    # ------------------------------------------------------------------

    async def _ensure_auth(self) -> None:
        if self._auth_configured:
            return
        if self._provider_id and self._api_key:
            try:
                await self._client.set_provider_auth(
                    self._provider_id, self._api_key
                )
                logger.info(
                    "Configured opencode provider auth: %s",
                    self._provider_id,
                )
            except Exception as e:
                logger.warning("Failed to set opencode provider auth: %s", e)
        self._auth_configured = True

    # ------------------------------------------------------------------
    # Tools exposed to the LLM-powered agent
    # ------------------------------------------------------------------

    def opencode_execute(self, task_description: str) -> str:
        """Execute a software development task using the OpenCode AI coding
        agent. OpenCode can read, search, edit, and write code across entire
        codebases. It has native file editing, code search, shell execution,
        and git integration.

        Use this tool for coding tasks such as:
        - Implementing new features or fixing bugs
        - Refactoring or restructuring code
        - Writing tests
        - Setting up projects and configurations
        - Code review and analysis

        Args:
            task_description: A detailed description of the coding task to
                accomplish. Be specific about files, languages, and expected
                outcomes.

        Returns:
            A summary of what OpenCode did, including files changed and any
            relevant output.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._execute_async(task_description)
        )

    def opencode_message(self, message: str) -> str:
        """Send a follow-up message to the active OpenCode session. Use this
        to provide clarification, request changes, or guide the coding agent
        after an initial ``opencode_execute`` call.

        Args:
            message: The follow-up instruction or clarification.

        Returns:
            The OpenCode agent's response summary.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._message_async(message)
        )

    def opencode_abort(self) -> str:
        """Abort the currently running OpenCode session. Use this if the
        coding agent is taking too long or going in the wrong direction.

        Returns:
            Confirmation that the session was aborted.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._abort_async()
        )

    def opencode_diff(self) -> str:
        """Get the file diffs from the current OpenCode session. Shows what
        files were changed and how.

        Returns:
            A formatted diff summary showing all file changes.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._diff_async()
        )

    # ------------------------------------------------------------------
    # Async implementations
    # ------------------------------------------------------------------

    async def _execute_async(self, task_description: str) -> str:
        # Ensure opencode is healthy
        if not await self._client.health():
            return (
                "Error: OpenCode server is not reachable at "
                f"{self._client._base_url}. "
                "The service may not be running."
            )

        await self._ensure_auth()

        # Create a new session for this task
        try:
            session_data = await self._client.create_session(
                title=task_description[:80],
            )
            self._session_id = session_data.get("id") or session_data.get(
                "info", {}
            ).get("id")
        except Exception as e:
            return f"Error creating OpenCode session: {e}"

        if not self._session_id:
            return "Error: Failed to obtain session ID from OpenCode."

        # Start event bridge for real-time SSE translation
        task_lock = TaskLock.get(self.api_task_id)
        if task_lock:
            self._bridge = OpenCodeEventBridge(
                client=self._client,
                task_lock=task_lock,
                agent_name=self.agent_name,
                agent_id=self._agent_id,
                process_task_id=self._process_task_id,
            )
            self._bridge.start(self._session_id)

        # Send the task as an async prompt
        try:
            await self._client.send_message_async(
                self._session_id,
                task_description,
                provider_id=self._provider_id,
                model_id=self._model_id,
            )
        except Exception as e:
            await self._cleanup_bridge()
            return f"Error sending message to OpenCode: {e}"

        # Wait for the session to become idle (task complete)
        if self._bridge:
            completed = await self._bridge.wait_for_idle(
                timeout=_IDLE_TIMEOUT
            )
            if not completed:
                await self._cleanup_bridge()
                return (
                    "OpenCode did not finish within the timeout. "
                    "The session may still be running. "
                    f"Session ID: {self._session_id}"
                )

        # Gather result summary
        return await self._build_summary()

    async def _message_async(self, message: str) -> str:
        if not self._session_id:
            return "Error: No active OpenCode session. Call opencode_execute first."

        await self._ensure_auth()

        # Restart bridge if not running
        task_lock = TaskLock.get(self.api_task_id)
        if task_lock and (self._bridge is None):
            self._bridge = OpenCodeEventBridge(
                client=self._client,
                task_lock=task_lock,
                agent_name=self.agent_name,
                agent_id=self._agent_id,
                process_task_id=self._process_task_id,
            )
            self._bridge.start(self._session_id)

        try:
            await self._client.send_message_async(
                self._session_id,
                message,
                provider_id=self._provider_id,
                model_id=self._model_id,
            )
        except Exception as e:
            return f"Error sending follow-up to OpenCode: {e}"

        if self._bridge:
            completed = await self._bridge.wait_for_idle(
                timeout=_IDLE_TIMEOUT
            )
            if not completed:
                return "OpenCode did not finish the follow-up within timeout."

        return await self._build_summary()

    async def _abort_async(self) -> str:
        if not self._session_id:
            return "No active OpenCode session to abort."
        try:
            await self._client.abort_session(self._session_id)
            await self._cleanup_bridge()
            return f"OpenCode session {self._session_id} aborted."
        except Exception as e:
            return f"Error aborting OpenCode session: {e}"

    async def _diff_async(self) -> str:
        if not self._session_id:
            return "No active OpenCode session."
        try:
            diff_data = await self._client.get_diff(self._session_id)
            if not diff_data:
                return "No file changes in the current session."
            # Format diff data
            lines: list[str] = []
            diffs = diff_data if isinstance(diff_data, list) else [diff_data]
            for d in diffs:
                if isinstance(d, dict):
                    path = d.get("path", d.get("file", "unknown"))
                    status = d.get("status", d.get("type", "modified"))
                    lines.append(f"  [{status}] {path}")
            return "File changes:\n" + "\n".join(lines) if lines else str(diff_data)
        except Exception as e:
            return f"Error getting diff: {e}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _build_summary(self) -> str:
        """Build a summary from the bridge's collected text and session diff."""
        parts: list[str] = []

        # Collected streaming text from the assistant
        if self._bridge and self._bridge.collected_text:
            parts.append(self._bridge.collected_text)

        # File changes
        diff_summary = await self._diff_async()
        if diff_summary and "No file changes" not in diff_summary:
            parts.append(f"\n{diff_summary}")

        if parts:
            return "\n".join(parts)

        return f"OpenCode session {self._session_id} completed (no output captured)."

    async def _cleanup_bridge(self) -> None:
        if self._bridge:
            await self._bridge.stop()
            self._bridge = None

    def set_process_task_id(self, task_id: str) -> None:
        """Set the hanggent process_task_id for SSE event correlation."""
        self._process_task_id = task_id
        if self._bridge:
            self._bridge._process_task_id = task_id

    async def cleanup(self) -> None:
        """Clean up resources: abort session if running, close HTTP client."""
        if self._session_id:
            try:
                await self._client.abort_session(self._session_id)
            except Exception:
                pass
        await self._cleanup_bridge()
        await self._client.close()

    def get_tools(self) -> list[FunctionTool]:
        return [
            FunctionTool(self.opencode_execute),
            FunctionTool(self.opencode_message),
            FunctionTool(self.opencode_abort),
            FunctionTool(self.opencode_diff),
        ]
