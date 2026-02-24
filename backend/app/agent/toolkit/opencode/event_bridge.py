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
Event bridge that translates OpenCode's SSE events into Hanggent's
SSE action protocol and pushes them onto a ``TaskLock.queue``.

Lifecycle:
    - ``start(session_id)`` — begin listening for events from that session
    - ``stop()`` — cancel the background listener task
    - ``wait_for_idle()`` — block until the session becomes idle

OpenCode event → Hanggent action mapping:
    session.status (busy)            → ActionActivateAgentData
    session.status (idle)            → ActionDeactivateAgentData
    message.part.updated (tool run)  → ActionActivateToolkitData
    message.part.updated (tool done) → ActionDeactivateToolkitData
    message.part.updated (bash meta) → ActionTerminalData (delta)
    file.edited                      → ActionWriteFileData
    write/edit tool completed        → ActionWriteFileData
    message.part.updated (text)      → (stored for summary; streamed text)
    permission.asked                 → ActionAskData
    session.error                    → ActionNoticeData
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agent.toolkit.opencode.client import OpenCodeClient
from app.service.task import (
    Action,
    ActionActivateAgentData,
    ActionActivateToolkitData,
    ActionAskData,
    ActionDeactivateAgentData,
    ActionDeactivateToolkitData,
    ActionNoticeData,
    ActionTerminalData,
    ActionWriteFileData,
    TaskLock,
)

logger = logging.getLogger(__name__)


class OpenCodeEventBridge:
    """
    Subscribes to the OpenCode ``GET /event`` SSE stream and translates
    relevant events into Hanggent's ``Action*Data`` models, pushing them
    onto the target ``TaskLock.queue``.
    """

    def __init__(
        self,
        client: OpenCodeClient,
        task_lock: TaskLock,
        agent_name: str = "opencode_agent",
        agent_id: str = "",
        process_task_id: str = "",
    ):
        self._client = client
        self._task_lock = task_lock
        self._agent_name = agent_name
        self._agent_id = agent_id
        self._process_task_id = process_task_id

        self._session_id: str | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._idle_event = asyncio.Event()
        self._stopped = False

        # Track the last bash output per callID so we can compute deltas
        self._last_bash_output: dict[str, str] = {}

        # Collect assistant text for final summary
        self._collected_text: list[str] = []

    @property
    def collected_text(self) -> str:
        """All streamed assistant text concatenated."""
        return "".join(self._collected_text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, session_id: str) -> None:
        """Begin listening for events from *session_id*."""
        self._session_id = session_id
        self._stopped = False
        self._idle_event.clear()
        self._listener_task = asyncio.create_task(
            self._listen(), name=f"opencode-event-bridge-{session_id}"
        )

    async def stop(self) -> None:
        """Cancel the listener task."""
        self._stopped = True
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        self._listener_task = None

    async def wait_for_idle(self, timeout: float = 600.0) -> bool:
        """
        Block until the tracked session emits ``session.status`` → idle.

        Returns ``True`` if idle, ``False`` on timeout.
        """
        try:
            await asyncio.wait_for(self._idle_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ------------------------------------------------------------------
    # Event listener loop
    # ------------------------------------------------------------------

    async def _listen(self) -> None:
        try:
            async for event in self._client.stream_events():
                if self._stopped:
                    break
                await self._handle_event(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("OpenCode event bridge error: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Event dispatcher
    # ------------------------------------------------------------------

    async def _handle_event(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", {})
        event_type: str = payload.get("type", "")
        props: dict[str, Any] = payload.get("properties", {})

        # Filter by session if available
        session_id_in_event = (
            props.get("sessionID")
            or props.get("info", {}).get("sessionID")
            or (props.get("part", {}).get("sessionID") if "part" in props else None)
        )
        if (
            session_id_in_event
            and self._session_id
            and session_id_in_event != self._session_id
        ):
            return  # Not our session

        # Route
        if event_type == "session.status":
            await self._on_session_status(props)
        elif event_type == "message.part.updated":
            await self._on_part_updated(props)
        elif event_type == "file.edited":
            await self._on_file_edited(props)
        elif event_type == "permission.asked":
            await self._on_permission_asked(props)
        elif event_type == "session.error":
            await self._on_session_error(props)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _on_session_status(self, props: dict[str, Any]) -> None:
        status = props.get("status") or props.get("type", "")

        if status == "busy":
            await self._task_lock.put_queue(
                ActionActivateAgentData(
                    data={
                        "agent_name": self._agent_name,
                        "process_task_id": self._process_task_id,
                        "agent_id": self._agent_id,
                        "message": "OpenCode agent is working...",
                    }
                )
            )
        elif status == "idle":
            await self._task_lock.put_queue(
                ActionDeactivateAgentData(
                    data={
                        "agent_name": self._agent_name,
                        "agent_id": self._agent_id,
                        "process_task_id": self._process_task_id,
                        "message": "OpenCode agent completed.",
                        "tokens": 0,
                    }
                )
            )
            self._idle_event.set()

    async def _on_part_updated(self, props: dict[str, Any]) -> None:
        part = props.get("part", {})
        delta_text = props.get("delta")
        part_type = part.get("type", "")

        if part_type == "tool":
            await self._handle_tool_part(part)
        elif part_type == "text" and delta_text:
            self._collected_text.append(delta_text)

    async def _handle_tool_part(self, part: dict[str, Any]) -> None:
        state = part.get("state", {})
        tool_name = part.get("tool", "unknown")
        status = state.get("status", "")
        call_id = part.get("callID", "")

        if status == "running":
            # Tool started
            input_data = state.get("input", {})
            title = state.get("title", tool_name)
            await self._task_lock.put_queue(
                ActionActivateToolkitData(
                    data={
                        "agent_name": self._agent_name,
                        "toolkit_name": f"OpenCode {tool_name}",
                        "process_task_id": self._process_task_id,
                        "method_name": tool_name,
                        "message": title
                        or str(input_data)[:200],
                    }
                )
            )

            # For bash tool, start tracking output
            if tool_name == "bash":
                self._last_bash_output[call_id] = ""

        elif status in ("completed", "error"):
            output = state.get("output", state.get("error", ""))
            title = state.get("title", tool_name)
            metadata = state.get("metadata", {})

            # Deactivate tool
            await self._task_lock.put_queue(
                ActionDeactivateToolkitData(
                    data={
                        "agent_name": self._agent_name,
                        "toolkit_name": f"OpenCode {tool_name}",
                        "process_task_id": self._process_task_id,
                        "method_name": tool_name,
                        "message": title or output[:200],
                    }
                )
            )

            # Emit final terminal output for bash
            if tool_name == "bash" and output:
                await self._task_lock.put_queue(
                    ActionTerminalData(
                        process_task_id=self._process_task_id,
                        data=output,
                    )
                )
                self._last_bash_output.pop(call_id, None)

            # Emit write_file for write/edit tools
            if tool_name in ("write", "edit", "apply_patch"):
                filepath = (
                    metadata.get("filepath")
                    or state.get("input", {}).get("file_path")
                    or state.get("input", {}).get("filePath")
                    or ""
                )
                if filepath:
                    await self._task_lock.put_queue(
                        ActionWriteFileData(
                            process_task_id=self._process_task_id,
                            data=filepath,
                        )
                    )

        elif status == "pending":
            pass  # Tool queued, no action yet

        else:
            # Intermediate update (e.g., bash streaming output)
            metadata = state.get("metadata", {})
            if "output" in metadata and part.get("tool") == "bash":
                new_output = metadata["output"]
                prev_output = self._last_bash_output.get(call_id, "")
                if len(new_output) > len(prev_output):
                    delta = new_output[len(prev_output):]
                    self._last_bash_output[call_id] = new_output
                    await self._task_lock.put_queue(
                        ActionTerminalData(
                            process_task_id=self._process_task_id,
                            data=delta,
                        )
                    )

    async def _on_file_edited(self, props: dict[str, Any]) -> None:
        filepath = props.get("file", "")
        if filepath:
            await self._task_lock.put_queue(
                ActionWriteFileData(
                    process_task_id=self._process_task_id,
                    data=filepath,
                )
            )

    async def _on_permission_asked(self, props: dict[str, Any]) -> None:
        # Auto-approve permissions for automated execution.
        # In the future this could surface to the user via ActionAskData.
        question = props.get("description", "OpenCode requests permission")
        await self._task_lock.put_queue(
            ActionAskData(
                data={
                    "question": question,
                    "agent": self._agent_name,
                }
            )
        )

    async def _on_session_error(self, props: dict[str, Any]) -> None:
        error = str(props.get("error", "Unknown error"))
        await self._task_lock.put_queue(
            ActionNoticeData(
                process_task_id=self._process_task_id,
                data=f"OpenCode error: {error}",
            )
        )
