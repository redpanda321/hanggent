"""Sandbox client protocol and base implementation.

Defines the interface for sandbox environments that provide
isolated browser automation with VNC streaming.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("sandbox.client")


class SandboxStatus(str, Enum):
    """Sandbox lifecycle status."""
    CREATING = "creating"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class SandboxInfo:
    """Information about a sandbox instance."""
    sandbox_id: str
    status: SandboxStatus
    vnc_url: Optional[str] = None
    browser_api_url: Optional[str] = None
    created_at: Optional[str] = None
    work_dir: str = "/workspace"
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Check if sandbox is running."""
        return self.status == SandboxStatus.RUNNING

    @property
    def is_ready(self) -> bool:
        """Check if sandbox is ready for use (has browser API)."""
        return self.is_running and self.browser_api_url is not None


@dataclass
class SandboxConfig:
    """Configuration for creating a sandbox."""
    image: str = "ghcr.io/browser-use/browser-use:latest"
    work_dir: str = "/workspace"
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    timeout: int = 3600  # 1 hour
    network_enabled: bool = True
    vnc_enabled: bool = True
    vnc_port: int = 6080
    vnc_password: Optional[str] = None
    browser_api_port: int = 8003
    environment: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)


@runtime_checkable
class SandboxClient(Protocol):
    """Protocol for sandbox client implementations.
    
    Sandbox clients manage the lifecycle of isolated execution
    environments for browser automation.
    """

    async def create(
        self,
        config: Optional[SandboxConfig] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> SandboxInfo:
        """Create a new sandbox instance.
        
        Args:
            config: Sandbox configuration options
            user_id: User ID for workspace isolation
            session_id: Session ID for workspace isolation
            
        Returns:
            SandboxInfo with sandbox details
        """
        ...

    async def start(self, sandbox_id: str) -> SandboxInfo:
        """Start a stopped sandbox.
        
        Args:
            sandbox_id: ID of the sandbox to start
            
        Returns:
            Updated SandboxInfo
        """
        ...

    async def stop(self, sandbox_id: str) -> SandboxInfo:
        """Stop a running sandbox.
        
        Args:
            sandbox_id: ID of the sandbox to stop
            
        Returns:
            Updated SandboxInfo
        """
        ...

    async def remove(self, sandbox_id: str) -> bool:
        """Remove a sandbox completely.
        
        Args:
            sandbox_id: ID of the sandbox to remove
            
        Returns:
            True if removal successful
        """
        ...

    async def get_status(self, sandbox_id: str) -> SandboxInfo:
        """Get current status of a sandbox.
        
        Args:
            sandbox_id: ID of the sandbox
            
        Returns:
            SandboxInfo with current status
        """
        ...

    async def get_vnc_url(self, sandbox_id: str) -> Optional[str]:
        """Get VNC URL for browser streaming.
        
        Args:
            sandbox_id: ID of the sandbox
            
        Returns:
            VNC websocket URL or None if not available
        """
        ...

    async def get_browser_api_url(self, sandbox_id: str) -> Optional[str]:
        """Get browser API URL for automation.
        
        Args:
            sandbox_id: ID of the sandbox
            
        Returns:
            Browser API URL or None if not available
        """
        ...

    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Execute a command inside the sandbox.
        
        Args:
            sandbox_id: ID of the sandbox
            command: Command to execute
            timeout: Execution timeout in seconds
            
        Returns:
            Dict with 'stdout', 'stderr', 'exit_code'
        """
        ...

    async def upload_file(
        self,
        sandbox_id: str,
        local_path: str,
        remote_path: str,
    ) -> bool:
        """Upload a file to the sandbox.
        
        Args:
            sandbox_id: ID of the sandbox
            local_path: Local file path
            remote_path: Destination path in sandbox
            
        Returns:
            True if upload successful
        """
        ...

    async def download_file(
        self,
        sandbox_id: str,
        remote_path: str,
        local_path: str,
    ) -> bool:
        """Download a file from the sandbox.
        
        Args:
            sandbox_id: ID of the sandbox
            remote_path: File path in sandbox
            local_path: Local destination path
            
        Returns:
            True if download successful
        """
        ...

    async def list_sandboxes(self) -> list[SandboxInfo]:
        """List all sandboxes.
        
        Returns:
            List of SandboxInfo for all sandboxes
        """
        ...

    async def cleanup_expired(self) -> int:
        """Cleanup expired sandboxes.
        
        Returns:
            Number of sandboxes cleaned up
        """
        ...


class BaseSandboxClient(ABC):
    """Base implementation for sandbox clients with common functionality."""

    def __init__(self):
        self._sandboxes: Dict[str, SandboxInfo] = {}

    def _register_sandbox(self, info: SandboxInfo) -> None:
        """Register a sandbox in the local cache."""
        self._sandboxes[info.sandbox_id] = info
        logger.debug(f"Registered sandbox: {info.sandbox_id}")

    def _unregister_sandbox(self, sandbox_id: str) -> None:
        """Unregister a sandbox from the local cache."""
        if sandbox_id in self._sandboxes:
            del self._sandboxes[sandbox_id]
            logger.debug(f"Unregistered sandbox: {sandbox_id}")

    def _get_cached_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]:
        """Get a sandbox from the local cache."""
        return self._sandboxes.get(sandbox_id)

    def _update_sandbox_status(
        self,
        sandbox_id: str,
        status: SandboxStatus,
        error_message: Optional[str] = None,
    ) -> Optional[SandboxInfo]:
        """Update sandbox status in cache."""
        if sandbox_id in self._sandboxes:
            self._sandboxes[sandbox_id].status = status
            if error_message:
                self._sandboxes[sandbox_id].error_message = error_message
            return self._sandboxes[sandbox_id]
        return None

    @abstractmethod
    async def create(
        self,
        config: Optional[SandboxConfig] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> SandboxInfo:
        """Create a new sandbox instance."""
        pass

    @abstractmethod
    async def start(self, sandbox_id: str) -> SandboxInfo:
        """Start a stopped sandbox."""
        pass

    @abstractmethod
    async def stop(self, sandbox_id: str) -> SandboxInfo:
        """Stop a running sandbox."""
        pass

    @abstractmethod
    async def remove(self, sandbox_id: str) -> bool:
        """Remove a sandbox completely."""
        pass

    @abstractmethod
    async def get_status(self, sandbox_id: str) -> SandboxInfo:
        """Get current status of a sandbox."""
        pass

    async def get_vnc_url(self, sandbox_id: str) -> Optional[str]:
        """Get VNC URL from cached sandbox info."""
        info = await self.get_status(sandbox_id)
        return info.vnc_url if info else None

    async def get_browser_api_url(self, sandbox_id: str) -> Optional[str]:
        """Get browser API URL from cached sandbox info."""
        info = await self.get_status(sandbox_id)
        return info.browser_api_url if info else None

    @abstractmethod
    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Execute a command inside the sandbox."""
        pass

    @abstractmethod
    async def upload_file(
        self,
        sandbox_id: str,
        local_path: str,
        remote_path: str,
    ) -> bool:
        """Upload a file to the sandbox."""
        pass

    @abstractmethod
    async def download_file(
        self,
        sandbox_id: str,
        remote_path: str,
        local_path: str,
    ) -> bool:
        """Download a file from the sandbox."""
        pass

    async def list_sandboxes(self) -> list[SandboxInfo]:
        """List all cached sandboxes."""
        return list(self._sandboxes.values())

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Cleanup expired sandboxes."""
        pass
