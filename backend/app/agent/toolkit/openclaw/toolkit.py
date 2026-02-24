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
OpenClawToolkit — CAMEL-compatible toolkit that bridges hanggent's workforce
agent system to the OpenClaw multi-channel messaging gateway.

Exposes tools for sending messages, managing channels & sessions, scheduling
cron tasks, invoking the gateway agent, and performing chat operations.
Under the hood it manages a hybrid WS+HTTP client with an event bridge that
translates OpenClaw events to hanggent SSE actions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from camel.toolkits import BaseToolkit, FunctionTool

from app.agent.toolkit.abstract_toolkit import AbstractToolkit
from app.agent.toolkit.openclaw.client import OpenClawClient
from app.agent.toolkit.openclaw.event_bridge import OpenClawEventBridge
from app.service.task import Agents, TaskLock

logger = logging.getLogger(__name__)

# Maximum time (seconds) to wait for a chat/agent run to complete.
_IDLE_TIMEOUT = 600.0


class OpenClawToolkit(BaseToolkit, AbstractToolkit):
    """Toolkit for controlling the OpenClaw messaging gateway."""

    agent_name: str = Agents.openclaw_agent  # type: ignore[assignment]

    def __init__(
        self,
        api_task_id: str,
        agent_name: str | None = None,
        openclaw_url: str | None = None,
        auth_token: str | None = None,
    ):
        super().__init__()

        self.api_task_id = api_task_id
        if agent_name is not None:
            self.agent_name = agent_name

        self._client = OpenClawClient(
            base_url=openclaw_url,
            auth_token=auth_token,
        )
        self._bridge: OpenClawEventBridge | None = None

    # ==================================================================
    # Tools exposed to the LLM-powered agent
    # ==================================================================

    def openclaw_send_message(
        self,
        to: str,
        message: str,
        channel: str = "",
        media_url: str = "",
    ) -> str:
        """Send an outbound message through a connected messaging channel
        (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, etc.).

        Args:
            to: The recipient identifier (phone number, username, channel
                ID, etc. depending on the messaging platform).
            message: The text message to send.
            channel: Optional channel name to send through (e.g.
                ``"whatsapp"``, ``"telegram"``). If empty, the gateway
                picks the best available channel.
            media_url: Optional URL of media to attach (image, document).

        Returns:
            Confirmation of the sent message or an error description.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._send_message_async(to, message, channel, media_url)
        )

    def openclaw_chat(
        self,
        message: str,
        session_key: str = "main",
    ) -> str:
        """Send a chat message to the OpenClaw AI agent within a session.
        The AI agent will process the message and respond using configured
        LLM models and tools.

        Use this for interactive AI conversations through the gateway.

        Args:
            message: The message to send to the AI agent.
            session_key: The session key to use (default ``"main"``).

        Returns:
            The AI agent's response text.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._chat_async(message, session_key)
        )

    def openclaw_chat_history(
        self, session_key: str = "main"
    ) -> str:
        """Retrieve the chat history for an OpenClaw session.

        Args:
            session_key: The session key (default ``"main"``).

        Returns:
            JSON-formatted chat history.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._chat_history_async(session_key)
        )

    def openclaw_channels_status(self) -> str:
        """Get the status of all connected messaging channels (WhatsApp,
        Telegram, Slack, Discord, etc.). Shows which channels are
        connected, disconnected, or have errors.

        Returns:
            A formatted summary of all channel statuses.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._channels_status_async()
        )

    def openclaw_sessions_list(self) -> str:
        """List all active sessions on the OpenClaw gateway.

        Returns:
            A formatted list of sessions with their keys and status.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._sessions_list_async()
        )

    def openclaw_cron_schedule(
        self,
        schedule: str,
        action_type: str,
        action_params: str = "{}",
        label: str = "",
    ) -> str:
        """Schedule a recurring cron task on the OpenClaw gateway.

        Args:
            schedule: Cron expression (e.g. ``"0 9 * * *"`` for 9am daily).
            action_type: The action to perform (e.g. ``"send"``,
                ``"agent"``).
            action_params: JSON string of action parameters.
            label: Optional human-readable label for the task.

        Returns:
            Confirmation with the created cron task ID.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._cron_schedule_async(
                schedule, action_type, action_params, label
            )
        )

    def openclaw_cron_list(self) -> str:
        """List all scheduled cron tasks on the OpenClaw gateway.

        Returns:
            A formatted list of cron tasks with schedules and labels.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._cron_list_async()
        )

    def openclaw_invoke_tool(
        self,
        tool: str,
        args: str = "{}",
        session_key: str = "main",
    ) -> str:
        """Invoke a specific tool on the OpenClaw gateway directly.

        Args:
            tool: The name of the tool to invoke.
            args: JSON string of arguments to pass to the tool.
            session_key: The session key context (default ``"main"``).

        Returns:
            The tool invocation result.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._invoke_tool_async(tool, args, session_key)
        )

    def openclaw_abort(self) -> str:
        """Abort the currently active chat or agent run on the gateway.

        Returns:
            Confirmation that the run was aborted.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._abort_async()
        )

    # ==================================================================
    # Async implementations
    # ==================================================================

    async def _send_message_async(
        self,
        to: str,
        message: str,
        channel: str,
        media_url: str,
    ) -> str:
        try:
            result = await self._client.send_message(
                to=to,
                message=message,
                channel=channel or None,
                media_url=media_url or None,
            )
            return (
                f"Message sent successfully to {to}"
                + (f" via {channel}" if channel else "")
                + f". Result: {json.dumps(result, default=str)}"
            )
        except Exception as e:
            return f"Error sending message: {e}"

    async def _chat_async(
        self, message: str, session_key: str
    ) -> str:
        # Health check
        if not await self._client.health_http():
            return (
                "Error: OpenClaw gateway is not reachable at "
                f"{self._client._base_url}. "
                "The service may not be running."
            )

        # Start event bridge for real-time translation
        task_lock = TaskLock.get(self.api_task_id)
        if task_lock and self._bridge is None:
            self._bridge = OpenClawEventBridge(
                client=self._client,
                task_lock=task_lock,
            )
            self._bridge.start()

        try:
            result = await self._client.chat_send(
                session_key=session_key,
                message=message,
            )
        except Exception as e:
            return f"Error sending chat message: {e}"

        # Wait for completion via event bridge
        if self._bridge:
            response_text = await self._bridge.wait_for_idle(
                timeout=_IDLE_TIMEOUT
            )
            if response_text:
                return response_text

        return json.dumps(result, default=str)

    async def _chat_history_async(self, session_key: str) -> str:
        try:
            history = await self._client.chat_history(session_key)
            return json.dumps(history, indent=2, default=str)
        except Exception as e:
            return f"Error retrieving chat history: {e}"

    async def _channels_status_async(self) -> str:
        try:
            channels = await self._client.channels_status()
            if not channels:
                return "No channels configured."
            lines: list[str] = ["Channel Status:"]
            for ch in channels if isinstance(channels, list) else [channels]:
                name = ch.get("name", ch.get("channel", "unknown"))
                status = ch.get("status", "unknown")
                emoji = (
                    "✓" if status == "connected" else
                    "✗" if status == "disconnected" else
                    "⚠"
                )
                lines.append(f"  {emoji} {name}: {status}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting channel status: {e}"

    async def _sessions_list_async(self) -> str:
        try:
            sessions = await self._client.sessions_list()
            if not sessions:
                return "No active sessions."
            lines: list[str] = ["Active Sessions:"]
            for s in (
                sessions if isinstance(sessions, list) else [sessions]
            ):
                key = s.get("sessionKey", s.get("key", "unknown"))
                msg_count = s.get("messageCount", "?")
                lines.append(f"  • {key} ({msg_count} messages)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing sessions: {e}"

    async def _cron_schedule_async(
        self,
        schedule: str,
        action_type: str,
        action_params: str,
        label: str,
    ) -> str:
        try:
            params = json.loads(action_params)
        except json.JSONDecodeError:
            return "Error: action_params must be valid JSON."
        try:
            action = {"type": action_type, **params}
            result = await self._client.cron_add(
                schedule=schedule,
                action=action,
                label=label or None,
            )
            cron_id = result.get("id", "unknown")
            return (
                f"Cron task created (ID: {cron_id}). "
                f"Schedule: {schedule}"
                + (f", Label: {label}" if label else "")
            )
        except Exception as e:
            return f"Error scheduling cron task: {e}"

    async def _cron_list_async(self) -> str:
        try:
            crons = await self._client.cron_list()
            if not crons:
                return "No scheduled cron tasks."
            lines: list[str] = ["Scheduled Cron Tasks:"]
            for c in crons if isinstance(crons, list) else [crons]:
                cron_id = c.get("id", "?")
                sched = c.get("schedule", "?")
                lbl = c.get("label", "")
                lines.append(
                    f"  • [{cron_id}] {sched}"
                    + (f" — {lbl}" if lbl else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing cron tasks: {e}"

    async def _invoke_tool_async(
        self, tool: str, args: str, session_key: str
    ) -> str:
        try:
            parsed_args = json.loads(args)
        except json.JSONDecodeError:
            return "Error: args must be valid JSON."
        try:
            result = await self._client.invoke_tool(
                tool=tool,
                args=parsed_args,
                session_key=session_key,
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error invoking tool '{tool}': {e}"

    async def _abort_async(self) -> str:
        if self._bridge and self._bridge._active_run_id:
            try:
                await self._client.chat_abort(
                    self._bridge._active_run_id
                )
                self._bridge.stop()
                self._bridge = None
                return "OpenClaw chat/agent run aborted."
            except Exception as e:
                return f"Error aborting run: {e}"
        return "No active OpenClaw run to abort."

    # ==================================================================
    # Lifecycle
    # ==================================================================

    async def cleanup(self) -> None:
        """Clean up resources: stop bridge, close connections."""
        if self._bridge:
            self._bridge.stop()
            self._bridge = None
        await self._client.close()

    def get_tools(self) -> list[FunctionTool]:
        return [
            FunctionTool(self.openclaw_send_message),
            FunctionTool(self.openclaw_chat),
            FunctionTool(self.openclaw_chat_history),
            FunctionTool(self.openclaw_channels_status),
            FunctionTool(self.openclaw_sessions_list),
            FunctionTool(self.openclaw_cron_schedule),
            FunctionTool(self.openclaw_cron_list),
            FunctionTool(self.openclaw_invoke_tool),
            FunctionTool(self.openclaw_abort),
        ]
