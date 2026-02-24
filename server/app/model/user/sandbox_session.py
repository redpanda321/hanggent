"""User sandbox session model for tracking active sandbox instances.

Stores sandbox session information for session persistence and reuse.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, text, Index
from sqlmodel import Field

from app.model.abstract.model import AbstractModel, DefaultTimes


class SandboxStatus(str, Enum):
    """Sandbox session status."""
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ARCHIVED = "archived"
    ERROR = "error"
    DELETED = "deleted"


class UserSandboxSession(AbstractModel, DefaultTimes, table=True):
    """Tracks active sandbox sessions per user.
    
    Enables session persistence - sandboxes stay alive between requests
    and can be reused until auto_stop_interval timeout.
    """
    __tablename__ = "user_sandbox_session"
    __table_args__ = (
        Index("ix_sandbox_session_user_status", "user_id", "status"),
        Index("ix_sandbox_session_daytona_id", "daytona_sandbox_id"),
    )
    
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    
    # Internal sandbox ID (our reference)
    sandbox_id: str = Field(
        max_length=64,
        index=True,
        description="Internal sandbox identifier"
    )
    
    # External Daytona sandbox ID
    daytona_sandbox_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Daytona platform sandbox ID"
    )
    
    # Session context (links sandbox to chat session if applicable)
    chat_session_id: Optional[str] = Field(
        default=None,
        max_length=64,
        index=True,
        description="Associated chat session ID"
    )
    
    # Sandbox status
    status: str = Field(
        default=SandboxStatus.CREATING.value,
        max_length=20,
        description="Current sandbox status"
    )
    
    # Connection URLs
    vnc_url: Optional[str] = Field(
        default=None,
        max_length=512,
        description="noVNC WebSocket URL for browser streaming"
    )
    browser_api_url: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Browser automation API URL"
    )
    
    # Workspace path inside sandbox
    workspace_path: Optional[str] = Field(
        default="/workspace",
        max_length=255,
        description="Working directory inside sandbox"
    )
    
    # Activity tracking for auto-stop
    last_activity_at: datetime = Field(
        sa_column=Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        description="Last activity timestamp"
    )
    
    # Expiration (based on auto_stop_interval)
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, nullable=True),
        description="When sandbox will auto-stop"
    )
    
    # Resource snapshot (what was allocated)
    cpu_allocated: Optional[int] = Field(
        default=None,
        description="CPU cores allocated"
    )
    memory_allocated_gb: Optional[int] = Field(
        default=None,
        description="Memory allocated in GB"
    )
    
    # Error information
    error_message: Optional[str] = Field(
        default=None,
        max_length=1024,
        description="Error message if status is ERROR"
    )
    
    def touch(self, auto_stop_minutes: int = 15) -> None:
        """Update last activity and extend expiration."""
        from datetime import timedelta
        self.last_activity_at = datetime.utcnow()
        self.expires_at = self.last_activity_at + timedelta(minutes=auto_stop_minutes)
    
    def mark_running(self, vnc_url: str = None, browser_api_url: str = None) -> None:
        """Mark sandbox as running with URLs."""
        self.status = SandboxStatus.RUNNING.value
        if vnc_url:
            self.vnc_url = vnc_url
        if browser_api_url:
            self.browser_api_url = browser_api_url
        self.touch()
    
    def mark_stopped(self) -> None:
        """Mark sandbox as stopped."""
        self.status = SandboxStatus.STOPPED.value
    
    def mark_error(self, message: str) -> None:
        """Mark sandbox as error."""
        self.status = SandboxStatus.ERROR.value
        self.error_message = message
    
    @classmethod
    def get_active_for_user(cls, user_id: int) -> list["UserSandboxSession"]:
        """Get all active (non-deleted) sessions for a user."""
        return cls.all(
            user_id=user_id,
            status__in=[SandboxStatus.RUNNING.value, SandboxStatus.STOPPED.value]
        ) or []
    
    @classmethod
    def get_running_for_user(cls, user_id: int) -> Optional["UserSandboxSession"]:
        """Get a running session for reuse."""
        sessions = cls.all(user_id=user_id, status=SandboxStatus.RUNNING.value)
        return sessions[0] if sessions else None
    
    @classmethod
    def get_by_sandbox_id(cls, sandbox_id: str) -> Optional["UserSandboxSession"]:
        """Get session by internal sandbox ID."""
        return cls.first(sandbox_id=sandbox_id)
    
    @classmethod
    def get_by_daytona_id(cls, daytona_id: str) -> Optional["UserSandboxSession"]:
        """Get session by Daytona sandbox ID."""
        return cls.first(daytona_sandbox_id=daytona_id)
