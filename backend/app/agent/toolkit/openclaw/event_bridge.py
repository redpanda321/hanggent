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
Event bridge that translates OpenClaw's WS push events into Hanggent's
SSE action protocol and pushes them onto a ``TaskLock.queue``.

Lifecycle:
    - ``start()`` — begin listening for WS events
    - ``stop()`` — cancel the background listener task
    - ``wait_for_idle(timeout)`` — block until the agent run completes

OpenClaw event → Hanggent action mapping:
    chat (delta)               → text collection (streamed to client)
    chat (final)               → ActionDeactivateAgentData
    chat (error/aborted)       → ActionNoticeData
    agent (started)            → ActionActivateAgentData
    agent (completed)          → ActionDeactivateAgentData
    send (confirmed)           → ActionTerminalData
    health (change)            → ActionNoticeData
    exec.approval.requested    → ActionAskData
    channel (incoming)         → ActionNoticeData
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agent.toolkit.openclaw.client import OpenClawClient
from app.service.task import (
    Action,
    ActionActivateAgentData,
    ActionActivateToolkitData,
    ActionAskData,
    ActionDeactivateAgentData,
    ActionDeactivateToolkitData,
    ActionNoticeData,
    ActionTerminalData,
    Agents,
    Status,
    TaskLock,
)

logger = logging.getLogger(__name__)


class OpenClawEventBridge:
    """Bridges OpenClaw WS events → Hanggent SSE action queue."""

    agent_name = Agents.openclaw_agent

    def __init__(
        self,
        client: OpenClawClient,
        task_lock: TaskLock,
    ):
        self._client = client
        self._task_lock = task_lock
        self._listener_task: asyncio.Task | None = None
        self._idle_event = asyncio.Event()
        self._event_queue: asyncio.Queue[dict[str, Any]] | None = None
        self._collected_text: list[str] = []
        self._active_run_id: str | None = None

    @property
    def collected_text(self) -> str:
        """Return all collected text from chat delta events."""
        return "".join(self._collected_text)

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def start(self) -> None:
        """Begin listening for OpenClaw WS events."""
        if self._listener_task and not self._listener_task.done():
            return

        self._idle_event.clear()
        self._collected_text.clear()
        self._event_queue = self._client.subscribe_events()
        self._listener_task = asyncio.create_task(
            self._listen(), name="openclaw-event-bridge"
        )

    def stop(self) -> None:
        """Cancel the background listener."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
        if self._event_queue:
            self._client.unsubscribe_events(self._event_queue)
            self._event_queue = None
        self._idle_event.set()

    async def wait_for_idle(self, timeout: float = 600.0) -> str:
        """Block until the active run completes or times out.

        Returns the collected text from chat events.
        """
        try:
            await asyncio.wait_for(
                self._idle_event.wait(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "OpenClaw event bridge timed out after %ss", timeout
            )
            self._push_notice(
                "OpenClaw agent run timed out", level="warning"
            )
        return self.collected_text

    # ==================================================================
    # Internal listener
    # ==================================================================

    async def _listen(self) -> None:
        """Main event loop — reads from subscription queue."""
        try:
            while True:
                assert self._event_queue is not None
                frame = await self._event_queue.get()
                try:
                    self._handle_frame(frame)
                except Exception:
                    logger.exception(
                        "Error handling OpenClaw event frame: %s",
                        str(frame)[:300],
                    )
        except asyncio.CancelledError:
            logger.debug("OpenClaw event bridge cancelled")
        except Exception:
            logger.exception("OpenClaw event bridge crashed")
        finally:
            self._idle_event.set()

    # ==================================================================
    # Frame dispatch
    # ==================================================================

    def _handle_frame(self, frame: dict[str, Any]) -> None:
        """Dispatch a single WS frame to the appropriate handler."""
        frame_type = frame.get("type")
        event_name = frame.get("event", "")
        payload = frame.get("payload", {})

        if frame_type == "event":
            self._handle_event(event_name, payload)
        elif frame_type == "push":
            # Push frames from chat.send (deltas, final, etc.)
            push_type = payload.get("type", "")
            self._handle_push(push_type, payload)

    def _handle_event(
        self, event: str, payload: dict[str, Any]
    ) -> None:
        """Handle an event-type frame."""
        if event == "chat":
            self._on_chat_event(payload)
        elif event == "agent.started":
            self._on_agent_started(payload)
        elif event == "agent.completed":
            self._on_agent_completed(payload)
        elif event == "agent.error":
            self._on_agent_error(payload)
        elif event == "exec.approval.requested":
            self._on_exec_approval(payload)
        elif event == "send.confirmed":
            self._on_send_confirmed(payload)
        elif event == "send.failed":
            self._on_send_failed(payload)
        elif event == "channel.incoming":
            self._on_channel_incoming(payload)
        elif event == "health":
            self._on_health(payload)
        elif event == "cron.triggered":
            self._on_cron_triggered(payload)
        else:
            logger.debug("OpenClaw unhandled event: %s", event)

    def _handle_push(
        self, push_type: str, payload: dict[str, Any]
    ) -> None:
        """Handle a push-type frame (chat stream)."""
        if push_type == "delta":
            self._on_chat_delta(payload)
        elif push_type == "final":
            self._on_chat_final(payload)
        elif push_type == "error":
            self._on_chat_error(payload)
        elif push_type == "aborted":
            self._on_chat_aborted(payload)

    # ==================================================================
    # Chat event handlers
    # ==================================================================

    def _on_chat_event(self, payload: dict[str, Any]) -> None:
        """Handle generic chat events."""
        status = payload.get("status")
        if status == "delta":
            self._on_chat_delta(payload)
        elif status == "final":
            self._on_chat_final(payload)
        elif status == "error":
            self._on_chat_error(payload)
        elif status == "aborted":
            self._on_chat_aborted(payload)

    def _on_chat_delta(self, payload: dict[str, Any]) -> None:
        """Collect streaming text from chat."""
        text = payload.get("text", payload.get("content", ""))
        if text:
            self._collected_text.append(text)

    def _on_chat_final(self, payload: dict[str, Any]) -> None:
        """Chat run completed successfully."""
        text = payload.get("text", payload.get("content", ""))
        if text:
            self._collected_text.append(text)

        self._push_action(
            ActionDeactivateAgentData(
                action=Action.deactivate_agent,
                agent=str(self.agent_name),
                status=Status.completed,
                message="Chat completed",
            )
        )
        self._idle_event.set()

    def _on_chat_error(self, payload: dict[str, Any]) -> None:
        """Chat run encountered an error."""
        error_msg = payload.get(
            "error", payload.get("message", "Unknown error")
        )
        self._push_notice(
            f"OpenClaw chat error: {error_msg}", level="error"
        )
        self._idle_event.set()

    def _on_chat_aborted(self, payload: dict[str, Any]) -> None:
        """Chat run was aborted."""
        self._push_notice("OpenClaw chat aborted", level="warning")
        self._idle_event.set()

    # ==================================================================
    # Agent event handlers
    # ==================================================================

    def _on_agent_started(self, payload: dict[str, Any]) -> None:
        """Agent invocation started."""
        run_id = payload.get("runId", "")
        self._active_run_id = run_id
        self._push_action(
            ActionActivateAgentData(
                action=Action.activate_agent,
                agent=str(self.agent_name),
                status=Status.running,
                message=f"Agent run started: {run_id}",
            )
        )

    def _on_agent_completed(self, payload: dict[str, Any]) -> None:
        """Agent invocation completed."""
        self._push_action(
            ActionDeactivateAgentData(
                action=Action.deactivate_agent,
                agent=str(self.agent_name),
                status=Status.completed,
                message="Agent run completed",
            )
        )
        self._active_run_id = None
        self._idle_event.set()

    def _on_agent_error(self, payload: dict[str, Any]) -> None:
        """Agent invocation error."""
        error_msg = payload.get("error", "Agent error")
        self._push_notice(
            f"OpenClaw agent error: {error_msg}", level="error"
        )
        self._active_run_id = None
        self._idle_event.set()

    # ==================================================================
    # Send event handlers
    # ==================================================================

    def _on_send_confirmed(self, payload: dict[str, Any]) -> None:
        """Outbound message was sent successfully."""
        to = payload.get("to", "")
        channel = payload.get("channel", "")
        self._push_action(
            ActionTerminalData(
                action=Action.terminal,
                agent=str(self.agent_name),
                content=f"✓ Message sent to {to} via {channel}",
            )
        )

    def _on_send_failed(self, payload: dict[str, Any]) -> None:
        """Outbound message failed to send."""
        error = payload.get("error", "Send failed")
        self._push_notice(
            f"Failed to send message: {error}", level="error"
        )

    # ==================================================================
    # Channel event handlers
    # ==================================================================

    def _on_channel_incoming(self, payload: dict[str, Any]) -> None:
        """Incoming message from a channel."""
        sender = payload.get("from", "unknown")
        channel = payload.get("channel", "unknown")
        preview = payload.get("text", "")[:100]
        self._push_notice(
            f"Incoming from {sender} ({channel}): {preview}",
            level="info",
        )

    # ==================================================================
    # Misc event handlers
    # ==================================================================

    def _on_health(self, payload: dict[str, Any]) -> None:
        """Health status change."""
        status = payload.get("status", "unknown")
        self._push_notice(
            f"OpenClaw health: {status}", level="info"
        )

    def _on_exec_approval(self, payload: dict[str, Any]) -> None:
        """Execution approval requested — prompt user."""
        approval_id = payload.get("id", "")
        command = payload.get("command", "unknown command")
        self._push_action(
            ActionAskData(
                action=Action.ask,
                agent=str(self.agent_name),
                question=(
                    f"OpenClaw requests approval to execute: "
                    f"`{command}`\n\n"
                    f"Approval ID: {approval_id}"
                ),
            )
        )

    def _on_cron_triggered(self, payload: dict[str, Any]) -> None:
        """Cron task was triggered."""
        label = payload.get("label", "unnamed")
        self._push_notice(
            f"Cron task triggered: {label}", level="info"
        )

    # ==================================================================
    # Helpers
    # ==================================================================

    def _push_action(self, data: Any) -> None:
        """Push an action onto the task lock queue."""
        try:
            self._task_lock.queue.put_nowait(data)
        except Exception:
            logger.warning(
                "Failed to push OpenClaw action to queue"
            )

    def _push_notice(
        self, message: str, level: str = "info"
    ) -> None:
        """Push a notice action."""
        self._push_action(
            ActionNoticeData(
                action=Action.notice,
                agent=str(self.agent_name),
                notice=message,
                level=level,
            )
        )
