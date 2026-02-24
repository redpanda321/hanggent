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
Generic IM Channel ↔ Hanggent User mapping.

Replaces the Telegram-only ``TelegramUserMapping`` with a polymorphic table
that supports any IM channel (Telegram, Discord, Slack, WhatsApp, LINE,
Feishu, Signal, IRC, Matrix, MS Teams, etc.).

When a user messages the shared Hanggent bot on any supported IM platform,
the webhook controller looks up this mapping.  If no mapping exists and
auto-registration is enabled, a new Hanggent user account is created
together with a mapping row — giving the IM user immediate access to
the AI assistant.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, UniqueConstraint
from sqlmodel import Column, Field

from app.model.abstract.model import AbstractModel, DefaultTimes


class ChannelUserMapping(AbstractModel, DefaultTimes, table=True):
    """Maps an IM channel identity to a Hanggent user.

    Unique constraint: (channel_type, channel_user_id) — one IM identity
    maps to exactly one Hanggent user.
    """

    __tablename__ = "channel_user_mapping"
    __table_args__ = (
        UniqueConstraint("channel_type", "channel_user_id", name="uq_channel_identity"),
    )

    id: int = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
        description="Hanggent user ID that owns this mapping",
    )

    channel_type: str = Field(
        sa_column=Column(String(32), nullable=False, index=True),
        description=(
            "Channel identifier: telegram, discord, slack, whatsapp, "
            "line, feishu, signal, irc, matrix, msteams, googlechat, etc."
        ),
    )

    channel_user_id: str = Field(
        sa_column=Column(String(128), nullable=False, index=True),
        description=(
            "Platform-specific user/chat ID. "
            "Telegram: chat_id (stringified BigInt). "
            "Discord: user snowflake. Slack: user ID (U0XXXX). "
            "WhatsApp: phone E.164. LINE: userId. Feishu: open_id."
        ),
    )

    channel_username: str | None = Field(
        default=None,
        max_length=128,
        description="Human-readable username/handle at time of mapping",
    )

    channel_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description=(
            "Extra platform-specific data — display name, avatar URL, "
            "phone number, etc.  Stored for debugging / display."
        ),
    )

    auto_registered: bool = Field(
        default=False,
        description="True if this mapping was created by auto-registration (first message)",
    )

    linked_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the link was established",
    )


class ChannelLinkingCode(AbstractModel, DefaultTimes, table=True):
    """Temporary linking codes for any IM channel.

    A 6-digit code is generated for a user + target channel.
    The user sends ``/link <CODE>`` in the IM app; the webhook handler
    verifies the code and creates/updates a ``ChannelUserMapping``.
    Codes expire after 5 minutes.
    """

    __tablename__ = "channel_linking_code"

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, description="Hanggent user ID")
    channel_type: str = Field(
        sa_column=Column(String(32), nullable=False, index=True),
        description="Target channel (telegram, discord, slack, …)",
    )
    code: str = Field(
        sa_column=Column(String(16), unique=True, nullable=False),
        description="6-digit linking code",
    )
    expires_at: datetime = Field(description="When this code expires")
    used: bool = Field(default=False, description="Whether this code has been consumed")
