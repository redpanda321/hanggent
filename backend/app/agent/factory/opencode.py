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
Factory function for the OpenCode developer agent.

Creates a ``ListenChatAgent`` that delegates software development tasks to the
OpenCode coding agent server via ``OpenCodeToolkit``.  The opencode agent sits
alongside the existing ``developer_agent`` in the workforce; the coordinator
routes codebase-wide tasks (feature implementation, refactoring, debugging)
to opencode, while the original developer_agent handles GUI automation, web
deployment, and desktop tasks.
"""

from __future__ import annotations

import logging
import platform

from camel.messages import BaseMessage
from camel.toolkits import ToolkitMessageIntegration

from app.agent.agent_model import agent_model
from app.agent.prompt import OPENCODE_AGENT_SYS_PROMPT
from app.agent.toolkit.human_toolkit import HumanToolkit
from app.agent.toolkit.note_taking_toolkit import NoteTakingToolkit
from app.agent.toolkit.opencode.client import OpenCodeClient
from app.agent.toolkit.opencode.toolkit import OpenCodeToolkit
from app.agent.toolkit.screenshot_toolkit import ScreenshotToolkit
from app.agent.utils import NOW_STR
from app.model.chat import Chat
from app.service.task import Agents
from app.utils.file_utils import get_working_directory

logger = logging.getLogger(__name__)


async def opencode_agent(options: Chat) -> object:
    """Create the OpenCode developer agent.

    This agent delegates coding tasks to an external OpenCode server.  It maps
    hanggent's LLM provider configuration to opencode's provider system so
    that the same API keys and models are used.
    """
    working_directory = get_working_directory(options)
    logger.info(
        "Creating opencode agent for project: %s in directory: %s",
        options.project_id,
        working_directory,
    )

    # Map hanggent LLM config → opencode provider/model
    provider_id, model_id = OpenCodeClient.map_provider(
        model_platform=options.model_platform or "",
        model_type=options.model_type or "",
        api_key=options.api_key,
        api_url=getattr(options, "api_url", None),
    )

    # Message integration for user-facing notifications
    message_integration = ToolkitMessageIntegration(
        message_handler=HumanToolkit(
            options.project_id, Agents.opencode_agent
        ).send_message_to_user
    )

    # --- Toolkits ---

    opencode_toolkit = OpenCodeToolkit(
        api_task_id=options.project_id,
        agent_name=Agents.opencode_agent,
        provider_id=provider_id,
        model_id=model_id,
        api_key=options.api_key,
        api_url=getattr(options, "api_url", None),
        working_directory=working_directory,
    )
    opencode_toolkit = message_integration.register_toolkits(opencode_toolkit)

    note_toolkit = NoteTakingToolkit(
        api_task_id=options.project_id,
        agent_name=Agents.opencode_agent,
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
            options.project_id, Agents.opencode_agent
        ),
        *opencode_toolkit.get_tools(),
        *note_toolkit.get_tools(),
        *screenshot_toolkit.get_tools(),
    ]

    system_message = OPENCODE_AGENT_SYS_PROMPT.format(
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        working_directory=working_directory,
        now_str=NOW_STR,
    )

    return agent_model(
        Agents.opencode_agent,
        BaseMessage.make_assistant_message(
            role_name="OpenCode Agent",
            content=system_message,
        ),
        options,
        tools,
        tool_names=[
            HumanToolkit.toolkit_name(),
            OpenCodeToolkit.toolkit_name(),
            NoteTakingToolkit.toolkit_name(),
            ScreenshotToolkit.toolkit_name(),
        ],
    )
