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
Factory function for the OpenClaw messaging gateway agent.

Creates a ``ListenChatAgent`` that manages the OpenClaw multi-channel
messaging gateway.  The openclaw agent handles:
- Sending/receiving messages across WhatsApp, Telegram, Slack, Discord,
  Signal, iMessage, Google Chat, and other channels
- Managing gateway sessions, channels, and configuration
- Scheduling cron tasks for automated messaging
- Invoking the gateway's built-in AI agent for conversational flows
- Direct tool invocation on the gateway
"""

from __future__ import annotations

import logging
import platform

from camel.messages import BaseMessage
from camel.toolkits import ToolkitMessageIntegration

from app.agent.agent_model import agent_model
from app.agent.prompt import OPENCLAW_AGENT_SYS_PROMPT
from app.agent.toolkit.human_toolkit import HumanToolkit
from app.agent.toolkit.note_taking_toolkit import NoteTakingToolkit
from app.agent.toolkit.openclaw.toolkit import OpenClawToolkit
from app.agent.toolkit.screenshot_toolkit import ScreenshotToolkit
from app.agent.utils import NOW_STR
from app.model.chat import Chat
from app.service.task import Agents
from app.utils.file_utils import get_working_directory

logger = logging.getLogger(__name__)


async def openclaw_agent(options: Chat) -> object:
    """Create the OpenClaw messaging gateway agent.

    This agent controls the OpenClaw multi-channel messaging gateway,
    enabling the workforce to send and receive messages across WhatsApp,
    Telegram, Slack, Discord, and other platforms.
    """
    working_directory = get_working_directory(options)
    logger.info(
        "Creating openclaw agent for project: %s",
        options.project_id,
    )

    # Message integration for user-facing notifications
    message_integration = ToolkitMessageIntegration(
        message_handler=HumanToolkit(
            options.project_id, Agents.openclaw_agent
        ).send_message_to_user
    )

    # --- Toolkits ---

    openclaw_toolkit = OpenClawToolkit(
        api_task_id=options.project_id,
        agent_name=Agents.openclaw_agent,
    )
    openclaw_toolkit = message_integration.register_toolkits(
        openclaw_toolkit
    )

    note_toolkit = NoteTakingToolkit(
        api_task_id=options.project_id,
        agent_name=Agents.openclaw_agent,
        working_directory=working_directory,
    )
    note_toolkit = message_integration.register_toolkits(note_toolkit)

    screenshot_toolkit = ScreenshotToolkit(
        options.project_id, working_directory=working_directory
    )
    screenshot_toolkit = message_integration.register_toolkits(
        screenshot_toolkit
    )

    tools = [
        *HumanToolkit.get_can_use_tools(
            options.project_id, Agents.openclaw_agent
        ),
        *openclaw_toolkit.get_tools(),
        *note_toolkit.get_tools(),
        *screenshot_toolkit.get_tools(),
    ]

    system_message = OPENCLAW_AGENT_SYS_PROMPT.format(
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        working_directory=working_directory,
        now_str=NOW_STR,
    )

    return agent_model(
        Agents.openclaw_agent,
        BaseMessage.make_assistant_message(
            role_name="OpenClaw Agent",
            content=system_message,
        ),
        options,
        tools,
        tool_names=[
            HumanToolkit.toolkit_name(),
            OpenClawToolkit.toolkit_name(),
            NoteTakingToolkit.toolkit_name(),
            ScreenshotToolkit.toolkit_name(),
        ],
    )
