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
Telegram Chat ID ↔ Hanggent User mapping for the shared Hanggent Telegram bot.

When a user selects "shared bot" mode for Telegram, they link their Telegram chat ID
to their Hanggent account via a one-time linking code. Incoming Telegram webhook
updates are then routed to the correct user's OpenClaw gateway based on this mapping.
"""

from datetime import datetime

from sqlalchemy import BigInteger, String
from sqlmodel import Column, Field

from app.model.abstract.model import AbstractModel, DefaultTimes


class TelegramUserMapping(AbstractModel, DefaultTimes, table=True):
    """Maps a Telegram chat_id to a Hanggent user for the shared bot."""

    __tablename__ = "telegram_user_mapping"

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, description="Hanggent user ID")
    telegram_chat_id: int = Field(
        sa_column=Column(BigInteger, unique=True, index=True, nullable=False),
        description="Telegram chat ID (can be large)",
    )
    telegram_username: str | None = Field(
        default=None, max_length=128, description="Telegram @username at time of linking"
    )
    linked_at: datetime = Field(default_factory=datetime.utcnow, description="When the link was established")


class TelegramLinkingCode(AbstractModel, DefaultTimes, table=True):
    """Temporary linking codes for the Telegram shared bot flow.

    A 6-digit code is generated and tied to a user_id.
    The user sends `/link <CODE>` to the shared Hanggent Telegram bot.
    The webhook handler verifies the code and creates a TelegramUserMapping.
    Codes expire after 5 minutes.
    """

    __tablename__ = "telegram_linking_code"

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, description="Hanggent user ID")
    code: str = Field(
        sa_column=Column(String(16), unique=True, nullable=False),
        description="6-digit linking code",
    )
    expires_at: datetime = Field(description="When this code expires")
    used: bool = Field(default=False, description="Whether this code has been consumed")
