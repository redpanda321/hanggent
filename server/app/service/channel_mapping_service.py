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
Channel Mapping Service — CRUD operations for IM channel ↔ Hanggent user mappings.

Provides a thin data-access layer that all webhook controllers share
instead of each one doing its own SQL.
"""

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.model.user.channel_user_mapping import ChannelUserMapping

logger = logging.getLogger(__name__)


def find_user_by_channel(
    channel_type: str,
    channel_user_id: str,
    *,
    s: Session,
) -> ChannelUserMapping | None:
    """Look up a mapping by (channel_type, channel_user_id).

    Returns ``None`` when no mapping exists for this IM identity.
    """
    return s.exec(
        select(ChannelUserMapping)
        .where(ChannelUserMapping.channel_type == channel_type)
        .where(ChannelUserMapping.channel_user_id == str(channel_user_id))
        .where(ChannelUserMapping.deleted_at.is_(None))  # type: ignore[union-attr]
    ).first()


def create_mapping(
    user_id: int,
    channel_type: str,
    channel_user_id: str,
    *,
    channel_username: str | None = None,
    channel_metadata: dict[str, Any] | None = None,
    auto_registered: bool = False,
    s: Session,
) -> ChannelUserMapping:
    """Create a new channel → user mapping and commit."""
    mapping = ChannelUserMapping(
        user_id=user_id,
        channel_type=channel_type,
        channel_user_id=str(channel_user_id),
        channel_username=channel_username,
        channel_metadata=channel_metadata,
        auto_registered=auto_registered,
        linked_at=datetime.utcnow(),
    )
    s.add(mapping)
    s.commit()
    s.refresh(mapping)
    logger.info(
        "Channel mapping created",
        extra={
            "user_id": user_id,
            "channel": channel_type,
            "channel_user_id": channel_user_id,
            "auto_registered": auto_registered,
        },
    )
    return mapping


def find_mappings_by_user(user_id: int, *, s: Session) -> list[ChannelUserMapping]:
    """Return all (non-deleted) channel mappings for a Hanggent user."""
    return list(
        s.exec(
            select(ChannelUserMapping)
            .where(ChannelUserMapping.user_id == user_id)
            .where(ChannelUserMapping.deleted_at.is_(None))  # type: ignore[union-attr]
        ).all()
    )


def find_mappings_by_channel_type(
    user_id: int,
    channel_type: str,
    *,
    s: Session,
) -> ChannelUserMapping | None:
    """Return the mapping for a specific channel type and user (if any)."""
    return s.exec(
        select(ChannelUserMapping)
        .where(ChannelUserMapping.user_id == user_id)
        .where(ChannelUserMapping.channel_type == channel_type)
        .where(ChannelUserMapping.deleted_at.is_(None))  # type: ignore[union-attr]
    ).first()


def delete_mapping(mapping: ChannelUserMapping, *, s: Session) -> None:
    """Soft-delete a mapping."""
    mapping.deleted_at = datetime.utcnow()
    s.add(mapping)
    s.commit()
    logger.info(
        "Channel mapping deleted",
        extra={
            "mapping_id": mapping.id,
            "user_id": mapping.user_id,
            "channel": mapping.channel_type,
        },
    )


def update_mapping(
    mapping: ChannelUserMapping,
    *,
    channel_username: str | None = None,
    channel_metadata: dict[str, Any] | None = None,
    s: Session,
) -> ChannelUserMapping:
    """Update mutable fields on a mapping."""
    if channel_username is not None:
        mapping.channel_username = channel_username
    if channel_metadata is not None:
        mapping.channel_metadata = channel_metadata
    s.add(mapping)
    s.commit()
    s.refresh(mapping)
    return mapping
