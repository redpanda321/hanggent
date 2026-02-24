"""Application configuration for Hanggent backend.

Provides configuration classes for different operational modes (Electron vs Web)
and service URLs. Supports sandbox environments (Docker/Daytona), authentication,
file uploads with streaming, and workspace isolation.
"""

import os
import secrets
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("config")


class AppMode(str, Enum):
    """Application running mode."""
    ELECTRON = "electron"
    WEB = "web"


class SandboxType(str, Enum):
    """Sandbox environment type."""
    NONE = "none"
    DOCKER = "docker"
    DAYTONA = "daytona"


class BrowserConfig(BaseModel):
    """Configuration for browser automation."""
    # CDP settings (Electron mode)
    cdp_port: int = Field(default=9222, description="Chrome DevTools Protocol port")
    cdp_url: Optional[str] = Field(default=None, description="CDP WebSocket URL (overrides port)")
    
    # browser_use settings (Web mode)
    headless: bool = Field(default=True, description="Run browser in headless mode")
    browser_type: str = Field(default="chromium", description="Browser type: chromium, firefox, webkit")
    disable_security: bool = Field(default=False, description="Disable browser security features")
    
    # Display settings (Web mode with VNC)
    enable_vnc: bool = Field(default=False, description="Enable VNC for browser display in web mode")
    vnc_port: int = Field(default=5900, description="VNC server port")
    
    @property
    def cdp_endpoint(self) -> str:
        """Get CDP endpoint URL."""
        return self.cdp_url or f"http://localhost:{self.cdp_port}"


class SandboxConfig(BaseModel):
    """Configuration for sandbox environments (Docker/Daytona).
    
    Sandboxes provide isolated execution environments for browser automation
    in web mode, with VNC streaming for UI visibility.
    """
    # Sandbox type selection
    sandbox_type: SandboxType = Field(
        default=SandboxType.NONE,
        description="Sandbox type: none, docker, daytona"
    )
    
    # Common sandbox settings
    image: str = Field(
        default="ghcr.io/browser-use/browser-use:latest",
        description="Container image for sandbox"
    )
    work_dir: str = Field(
        default="/workspace",
        description="Working directory inside sandbox"
    )
    memory_limit: str = Field(
        default="512m",
        description="Memory limit for sandbox container"
    )
    cpu_limit: float = Field(
        default=1.0,
        description="CPU limit for sandbox container"
    )
    timeout: int = Field(
        default=3600,
        description="Sandbox timeout in seconds (default 1 hour)"
    )
    network_enabled: bool = Field(
        default=True,
        description="Enable network access in sandbox"
    )
    
    # VNC settings for browser streaming
    vnc_enabled: bool = Field(
        default=True,
        description="Enable VNC server for browser display"
    )
    vnc_port: int = Field(
        default=6080,
        description="noVNC web port (websocket)"
    )
    vnc_password: Optional[str] = Field(
        default=None,
        description="VNC password (auto-generated if not set)"
    )
    
    # Browser API port (for browser_use inside sandbox)
    browser_api_port: int = Field(
        default=8003,
        description="Browser API port inside sandbox"
    )


class DaytonaConfig(BaseModel):
    """Configuration for Daytona cloud sandbox.
    
    Daytona provides cloud-hosted sandbox environments with
    built-in VNC and browser automation support.
    
    Settings can be loaded from:
    1. Environment variables (HANGGENT_DAYTONA__*)
    2. Server API (per-user settings stored in DB)
    """
    api_key: Optional[str] = Field(
        default=None,
        description="Daytona API key (from env or user settings)"
    )
    server_url: str = Field(
        default="https://app.daytona.io",
        description="Daytona server URL"
    )
    organization_id: Optional[str] = Field(
        default=None,
        description="Daytona organization ID"
    )
    target: str = Field(
        default="us",
        description="Daytona target region: us, eu"
    )
    sandbox_image: str = Field(
        default="daytonaio/ai-sandbox:latest",
        description="Daytona sandbox image"
    )
    
    # Resource limits (Daytona defaults: 4GB RAM, 2 CPU)
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
    
    # VNC password
    vnc_password: Optional[str] = Field(
        default=None,
        description="VNC password for browser streaming"
    )
    
    @property
    def is_configured(self) -> bool:
        """Check if Daytona is properly configured."""
        return bool(self.api_key)
    
    @classmethod
    def from_user_settings(cls, settings: dict) -> "DaytonaConfig":
        """Create config from user settings dict (from server API).
        
        Args:
            settings: Dict with keys like api_key, server_url, cpu_limit, etc.
        """
        return cls(
            api_key=settings.get("api_key"),
            server_url=settings.get("server_url", "https://app.daytona.io"),
            target=settings.get("target", "us"),
            sandbox_image=settings.get("sandbox_image", "daytonaio/ai-sandbox:latest"),
            cpu_limit=settings.get("cpu_limit", 2),
            memory_limit_gb=settings.get("memory_limit_gb", 4),
            disk_limit_gb=settings.get("disk_limit_gb", 5),
            auto_stop_interval=settings.get("auto_stop_interval", 15),
            auto_archive_interval=settings.get("auto_archive_interval", 1440),
            vnc_password=settings.get("vnc_password"),
        )


class AuthConfig(BaseModel):
    """Configuration for JWT authentication with refresh tokens.
    
    In web mode, backend validates tokens issued by hanggent/server.
    Both backends must use the same secret_key for this to work.
    """
    # JWT settings - MUST match hanggent/server's secret_key in web mode
    secret_key: str = Field(
        default="",
        description="JWT secret key (REQUIRED in web mode - must match hanggent/server's secret_key)"
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    
    # Token expiration
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration in days"
    )
    
    # Token settings
    token_type: str = Field(
        default="bearer",
        description="Token type for Authorization header"
    )
    
    # Security settings
    require_auth: bool = Field(
        default=True,
        description="Require authentication for API endpoints"
    )
    
    def is_configured(self) -> bool:
        """Check if auth is properly configured with a secret key."""
        return bool(self.secret_key)
    
    @property
    def access_token_expire_seconds(self) -> int:
        """Get access token expiration in seconds."""
        return self.access_token_expire_minutes * 60
    
    @property
    def refresh_token_expire_seconds(self) -> int:
        """Get refresh token expiration in seconds."""
        return self.refresh_token_expire_days * 24 * 60 * 60


class ServerConfig(BaseModel):
    """Configuration for backend/server URLs."""
    backend_url: str = Field(
        default="http://localhost:5001",
        description="Hanggent backend API URL (FastAPI on port 5001)"
    )
    server_url: str = Field(
        default="http://localhost:3001",
        description="Hanggent server API URL (FastAPI on port 3001)"
    )
    api_timeout: float = Field(default=30.0, description="API request timeout in seconds")


class FileConfig(BaseModel):
    """Configuration for file operations with streaming upload support."""
    # Directory settings
    workspace_dir: str = Field(
        default="~/.hanggent/workspace",
        description="Default workspace directory"
    )
    temp_dir: str = Field(
        default="~/.hanggent/temp",
        description="Temporary files directory"
    )
    upload_dir: str = Field(
        default="~/.hanggent/uploads",
        description="Upload staging directory"
    )
    
    # File size limits
    max_file_size: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="Maximum file size for uploads"
    )
    chunk_size: int = Field(
        default=1024 * 1024,  # 1MB
        description="Chunk size for streaming uploads"
    )
    
    # Allowed file types
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [
            ".txt", ".md", ".json", ".yaml", ".yml",
            ".py", ".js", ".ts", ".jsx", ".tsx",
            ".html", ".css", ".scss",
            ".csv", ".xml",
            ".png", ".jpg", ".jpeg", ".gif", ".svg",
            ".pdf", ".doc", ".docx",
            ".zip", ".tar", ".gz"
        ],
        description="Allowed file extensions for upload"
    )
    
    # Security settings
    scan_uploads: bool = Field(
        default=True,
        description="Scan uploaded files for security"
    )
    
    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """Ensure max file size is reasonable."""
        if v < 1024:  # 1KB minimum
            raise ValueError("max_file_size must be at least 1KB")
        if v > 500 * 1024 * 1024:  # 500MB maximum
            raise ValueError("max_file_size cannot exceed 500MB")
        return v


class WorkspaceConfig(BaseModel):
    """Configuration for workspace isolation per user/session."""
    # Isolation settings
    enable_isolation: bool = Field(
        default=True,
        description="Enable per-user/session workspace isolation"
    )
    isolation_mode: str = Field(
        default="session",
        description="Isolation mode: 'user', 'session', 'project'"
    )
    
    # Workspace structure
    base_path: str = Field(
        default="~/.hanggent/workspaces",
        description="Base path for isolated workspaces"
    )
    
    # Cleanup settings
    auto_cleanup: bool = Field(
        default=True,
        description="Automatically cleanup old workspaces"
    )
    max_age_hours: int = Field(
        default=24,
        description="Maximum age for session workspaces before cleanup"
    )
    max_workspaces_per_user: int = Field(
        default=10,
        description="Maximum concurrent workspaces per user"
    )


class PlanningConfig(BaseModel):
    """Configuration for planning mode execution.
    
    Planning mode provides explicit step-by-step task execution with
    progress tracking, as an alternative to the default Workforce pattern.
    
    Settings can be loaded from:
    1. Environment variables (HANGGENT_PLANNING__*)
    2. TOML configuration file (~/.hanggent/config.toml or project-level)
    3. Server API (per-user settings)
    """
    # Planning mode settings
    enabled: bool = Field(
        default=False,
        description="Enable planning mode by default for complex tasks"
    )
    auto_detect: bool = Field(
        default=True,
        description="Automatically detect when to use planning mode"
    )
    
    # Plan creation settings
    max_plan_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum LLM calls to create a valid plan"
    )
    max_steps: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum steps allowed in a plan"
    )
    require_step_annotations: bool = Field(
        default=False,
        description="Require [AGENT_TYPE] annotations in steps"
    )
    
    # Execution settings
    max_step_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum retries per step on failure"
    )
    step_timeout_seconds: float = Field(
        default=300.0,
        ge=30.0,
        le=1800.0,
        description="Timeout per step execution in seconds"
    )
    parallel_steps: bool = Field(
        default=False,
        description="Allow parallel execution of independent steps"
    )
    
    # Agent routing
    default_agent: str = Field(
        default="opencode",
        description="Default agent for steps without [AGENT_TYPE] annotation"
    )
    
    # Progress tracking
    stream_progress: bool = Field(
        default=True,
        description="Stream progress updates to frontend"
    )
    generate_summary: bool = Field(
        default=True,
        description="Generate summary after plan completion"
    )
    
    # Default plan templates
    default_steps: list[str] = Field(
        default_factory=lambda: [
            "Analyze and understand the request",
            "Execute the main task",
            "Verify and validate results"
        ],
        description="Fallback steps if plan creation fails"
    )


class TomlConfig(BaseModel):
    """Configuration for TOML file loading support.
    
    Supports loading configuration from TOML files, similar to
    backend-manus config.toml format. Order of precedence:
    1. Environment variables (highest)
    2. Project-level .hanggent.toml
    3. User-level ~/.hanggent/config.toml
    4. Default values (lowest)
    """
    enabled: bool = Field(
        default=True,
        description="Enable TOML configuration file loading"
    )
    user_config_path: str = Field(
        default="~/.hanggent/config.toml",
        description="User-level TOML config file path"
    )
    project_config_name: str = Field(
        default=".hanggent.toml",
        description="Project-level TOML config filename"
    )
    auto_reload: bool = Field(
        default=False,
        description="Auto-reload config on file changes"
    )
    
    @property
    def user_config_expanded(self) -> str:
        """Get expanded user config path."""
        return os.path.expanduser(self.user_config_path)


class AppConfig(BaseSettings):
    """Main application configuration.
    
    Configuration can be set via:
    - Environment variables (prefixed with HANGGENT_)
    - .env file
    - Direct initialization
    
    Examples:
        HANGGENT_APP_MODE=web
        HANGGENT_BACKEND_URL=http://localhost:5001
        HANGGENT_CDP_PORT=9222
        HANGGENT_SANDBOX__SANDBOX_TYPE=daytona
        HANGGENT_AUTH__SECRET_KEY=your-secret-key
    """
    
    # Application mode
    app_mode: AppMode = Field(
        default=AppMode.ELECTRON,
        description="Application mode: 'electron' or 'web'"
    )
    
    # Debug settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Nested configurations
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    file: FileConfig = Field(default_factory=FileConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    daytona: DaytonaConfig = Field(default_factory=DaytonaConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    planning: PlanningConfig = Field(default_factory=PlanningConfig)
    toml_config: TomlConfig = Field(default_factory=TomlConfig)
    
    model_config = {
        "env_prefix": "HANGGENT_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }
    
    @property
    def is_electron_mode(self) -> bool:
        """Check if running in Electron mode."""
        return self.app_mode == AppMode.ELECTRON
    
    @property
    def is_web_mode(self) -> bool:
        """Check if running in Web mode."""
        return self.app_mode == AppMode.WEB
    
    @property
    def use_sandbox(self) -> bool:
        """Check if sandbox is enabled."""
        return self.sandbox.sandbox_type != SandboxType.NONE
    
    @property
    def use_daytona(self) -> bool:
        """Check if Daytona sandbox is configured."""
        return (
            self.sandbox.sandbox_type == SandboxType.DAYTONA
            and self.daytona.is_configured
        )
    
    @property
    def use_docker(self) -> bool:
        """Check if Docker sandbox is configured."""
        return self.sandbox.sandbox_type == SandboxType.DOCKER
    
    @property
    def use_planning_mode(self) -> bool:
        """Check if planning mode is enabled by default."""
        return self.planning.enabled
    
    @property
    def should_auto_detect_planning(self) -> bool:
        """Check if planning mode auto-detection is enabled."""
        return self.planning.auto_detect
    
    def get_workspace_path(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
        """Get expanded workspace path with optional isolation."""
        base = os.path.expanduser(self.file.workspace_dir)
        
        if not self.workspace.enable_isolation:
            return base
        
        # Apply isolation based on mode
        if self.workspace.isolation_mode == "user" and user_id:
            return os.path.join(base, f"user_{user_id}")
        elif self.workspace.isolation_mode == "session" and session_id:
            return os.path.join(base, f"session_{session_id}")
        elif self.workspace.isolation_mode == "project":
            # Project isolation handled separately
            return base
        
        return base
    
    def get_temp_path(self) -> str:
        """Get expanded temp path."""
        return os.path.expanduser(self.file.temp_dir)
    
    def get_upload_path(self) -> str:
        """Get expanded upload path."""
        return os.path.expanduser(self.file.upload_dir)


# Global configuration instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = AppConfig()
        logger.info(
            f"Configuration loaded: mode={_config.app_mode.value}, "
            f"backend={_config.server.backend_url}, "
            f"server={_config.server.server_url}"
        )
    return _config


def set_config(config: AppConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
    logger.info(f"Configuration updated: mode={config.app_mode.value}")


def reset_config() -> None:
    """Reset configuration to default."""
    global _config
    _config = None
