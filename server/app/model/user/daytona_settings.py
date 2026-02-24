"""User Daytona settings model for per-user API key and configuration storage.

Stores encrypted Daytona API keys and sandbox resource preferences per user.
"""

from typing import Optional

from sqlalchemy import Column, Integer, ForeignKey, String, UniqueConstraint
from sqlmodel import Field

from app.model.abstract.model import AbstractModel, DefaultTimes


class UserDaytonaSettings(AbstractModel, DefaultTimes, table=True):
    """Per-user Daytona configuration and credentials.
    
    Stores:
    - Encrypted Daytona API key (Fernet encrypted)
    - Server URL and target region
    - Resource limits (CPU, memory, disk)
    - Auto-stop/archive intervals
    """
    __tablename__ = "user_daytona_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uix_user_daytona_settings_user_id"),
    )
    
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    
    # Encrypted API key (use encrypt.encrypt_credential / decrypt_credential)
    encrypted_api_key: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Fernet-encrypted Daytona API key"
    )
    
    # Daytona server configuration
    server_url: str = Field(
        default="https://app.daytona.io",
        max_length=255,
        description="Daytona server URL"
    )
    target: str = Field(
        default="us",
        max_length=20,
        description="Daytona target region: us, eu"
    )
    
    # Resource limits (Daytona defaults)
    cpu_limit: int = Field(
        default=2,
        ge=1,
        le=8,
        description="CPU cores for sandbox (1-8)"
    )
    memory_limit_gb: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Memory limit in GB (1-16)"
    )
    disk_limit_gb: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Disk limit in GB (1-50)"
    )
    
    # Session persistence settings
    auto_stop_interval: int = Field(
        default=15,
        ge=5,
        le=120,
        description="Minutes of inactivity before auto-stop (5-120)"
    )
    auto_archive_interval: int = Field(
        default=1440,  # 24 hours
        ge=60,
        le=10080,  # 7 days
        description="Minutes before auto-archive (60-10080)"
    )
    
    # Custom sandbox image (optional)
    sandbox_image: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Custom sandbox Docker image (defaults to daytonaio/ai-sandbox:latest)"
    )
    
    # VNC password (optional, auto-generated if not set)
    vnc_password: Optional[str] = Field(
        default=None,
        max_length=64,
        description="VNC password for browser streaming"
    )
    
    @property
    def effective_image(self) -> str:
        """Get the effective sandbox image."""
        return self.sandbox_image or "daytonaio/ai-sandbox:latest"
    
    @classmethod
    def get_by_user_id(cls, user_id: int) -> Optional["UserDaytonaSettings"]:
        """Get settings for a user."""
        return cls.first(user_id=user_id)
    
    @classmethod
    def get_or_create(cls, user_id: int) -> "UserDaytonaSettings":
        """Get or create settings for a user with defaults."""
        settings = cls.first(user_id=user_id)
        if not settings:
            settings = cls(user_id=user_id)
            settings.save()
        return settings
