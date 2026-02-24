"""Refresh token model for JWT authentication.

Stores refresh tokens for users to enable token refresh without
re-authentication.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, text, Index
from sqlmodel import Field

from app.model.abstract.model import AbstractModel


class RefreshToken(AbstractModel, table=True):
    """Refresh token for JWT authentication.
    
    Refresh tokens are long-lived tokens that allow users to obtain
    new access tokens without re-authenticating.
    """
    __tablename__ = "refresh_token"
    
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    token_hash: str = Field(
        max_length=256,
        description="Hashed refresh token for secure storage"
    )
    device_info: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Device/browser info for token identification"
    )
    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,
        description="IP address where token was issued"
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime, nullable=False),
        description="Token expiration timestamp"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, nullable=True),
        description="Last time token was used for refresh"
    )
    is_revoked: bool = Field(
        default=False,
        sa_column=Column(Boolean, server_default=text("false")),
        description="Whether token has been revoked"
    )
    
    # Add indexes for common queries
    __table_args__ = (
        Index("idx_refresh_token_user_id", "user_id"),
        Index("idx_refresh_token_hash", "token_hash"),
        Index("idx_refresh_token_expires", "expires_at"),
    )
