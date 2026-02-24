"""Sandbox manager for coordinating sandbox lifecycle.

Provides a unified interface for managing sandboxes across different
providers (Docker, Daytona) based on configuration.
"""

import asyncio
from typing import Dict, Optional

from utils import traceroot_wrapper as traceroot

from app.config import SandboxType, get_config
from app.sandbox.client import (
    SandboxClient,
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)

logger = traceroot.get_logger("sandbox.manager")

# Global manager instance
_sandbox_manager: Optional["SandboxManager"] = None


class SandboxManager:
    """Unified sandbox manager supporting Docker and Daytona.
    
    Automatically selects the appropriate sandbox client based on
    configuration and provides lifecycle management.
    """

    def __init__(self):
        """Initialize sandbox manager."""
        self._client: Optional[SandboxClient] = None
        self._sandboxes: Dict[str, SandboxInfo] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._config = get_config()

    @property
    def client(self) -> SandboxClient:
        """Get the sandbox client (lazy initialization)."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> SandboxClient:
        """Create appropriate sandbox client based on configuration."""
        config = self._config
        sandbox_type = config.sandbox.sandbox_type

        if sandbox_type == SandboxType.DOCKER:
            from app.sandbox.docker_sandbox import DockerSandboxClient
            logger.info("Using Docker sandbox client")
            return DockerSandboxClient(
                host_vnc_port_start=config.sandbox.vnc_port,
                host_api_port_start=config.sandbox.browser_api_port,
            )

        elif sandbox_type == SandboxType.DAYTONA:
            if not config.daytona.is_configured:
                raise ValueError(
                    "Daytona sandbox requires HANGGENT_DAYTONA__API_KEY to be set"
                )
            from app.sandbox.daytona_sandbox import DaytonaSandboxClient
            logger.info("Using Daytona sandbox client")
            return DaytonaSandboxClient(
                api_key=config.daytona.api_key,
                server_url=config.daytona.server_url,
                organization_id=config.daytona.organization_id,
                target=config.daytona.target,
            )

        else:
            raise ValueError(f"Unsupported sandbox type: {sandbox_type}")

    @property
    def is_enabled(self) -> bool:
        """Check if sandbox is enabled."""
        return self._config.sandbox.sandbox_type != SandboxType.NONE

    @property
    def sandbox_type(self) -> SandboxType:
        """Get configured sandbox type."""
        return self._config.sandbox.sandbox_type

    async def create_sandbox(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
    ) -> SandboxInfo:
        """Create a new sandbox.
        
        Args:
            user_id: User ID for isolation
            session_id: Session ID for isolation
            config: Optional custom sandbox configuration
            
        Returns:
            SandboxInfo for the created sandbox
        """
        if not self.is_enabled:
            raise ValueError("Sandbox is not enabled in configuration")

        # Use default config from settings if not provided
        if config is None:
            app_config = self._config
            config = SandboxConfig(
                image=app_config.sandbox.image,
                work_dir=app_config.sandbox.work_dir,
                memory_limit=app_config.sandbox.memory_limit,
                cpu_limit=app_config.sandbox.cpu_limit,
                timeout=app_config.sandbox.timeout,
                network_enabled=app_config.sandbox.network_enabled,
                vnc_enabled=app_config.sandbox.vnc_enabled,
                vnc_port=app_config.sandbox.vnc_port,
                vnc_password=app_config.sandbox.vnc_password,
                browser_api_port=app_config.sandbox.browser_api_port,
            )

        info = await self.client.create(
            config=config,
            user_id=user_id,
            session_id=session_id,
        )

        self._sandboxes[info.sandbox_id] = info
        logger.info(f"Created sandbox: {info.sandbox_id} (type: {self.sandbox_type.value})")
        return info

    async def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]:
        """Get sandbox info by ID.
        
        Args:
            sandbox_id: Sandbox ID
            
        Returns:
            SandboxInfo or None if not found
        """
        if sandbox_id in self._sandboxes:
            # Refresh status
            info = await self.client.get_status(sandbox_id)
            self._sandboxes[sandbox_id] = info
            return info
        return None

    async def start_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """Start a stopped sandbox.
        
        Args:
            sandbox_id: Sandbox ID to start
            
        Returns:
            Updated SandboxInfo
        """
        info = await self.client.start(sandbox_id)
        self._sandboxes[sandbox_id] = info
        logger.info(f"Started sandbox: {sandbox_id}")
        return info

    async def stop_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """Stop a running sandbox.
        
        Args:
            sandbox_id: Sandbox ID to stop
            
        Returns:
            Updated SandboxInfo
        """
        info = await self.client.stop(sandbox_id)
        self._sandboxes[sandbox_id] = info
        logger.info(f"Stopped sandbox: {sandbox_id}")
        return info

    async def remove_sandbox(self, sandbox_id: str) -> bool:
        """Remove a sandbox completely.
        
        Args:
            sandbox_id: Sandbox ID to remove
            
        Returns:
            True if removal successful
        """
        result = await self.client.remove(sandbox_id)
        if result and sandbox_id in self._sandboxes:
            del self._sandboxes[sandbox_id]
        logger.info(f"Removed sandbox: {sandbox_id}")
        return result

    async def get_vnc_url(self, sandbox_id: str) -> Optional[str]:
        """Get VNC streaming URL for a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            
        Returns:
            VNC websocket URL or None
        """
        return await self.client.get_vnc_url(sandbox_id)

    async def get_browser_api_url(self, sandbox_id: str) -> Optional[str]:
        """Get browser automation API URL for a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            
        Returns:
            Browser API URL or None
        """
        return await self.client.get_browser_api_url(sandbox_id)

    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = 60,
    ) -> Dict[str, any]:
        """Execute a command inside a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            command: Command to execute
            timeout: Execution timeout
            
        Returns:
            Dict with stdout, stderr, exit_code
        """
        return await self.client.execute_command(sandbox_id, command, timeout)

    async def upload_file(
        self,
        sandbox_id: str,
        local_path: str,
        remote_path: str,
    ) -> bool:
        """Upload a file to a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            local_path: Local file path
            remote_path: Destination in sandbox
            
        Returns:
            True if upload successful
        """
        return await self.client.upload_file(sandbox_id, local_path, remote_path)

    async def download_file(
        self,
        sandbox_id: str,
        remote_path: str,
        local_path: str,
    ) -> bool:
        """Download a file from a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            remote_path: File path in sandbox
            local_path: Local destination path
            
        Returns:
            True if download successful
        """
        return await self.client.download_file(sandbox_id, remote_path, local_path)

    async def list_sandboxes(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[SandboxInfo]:
        """List all sandboxes, optionally filtered.
        
        Args:
            user_id: Filter by user ID
            session_id: Filter by session ID
            
        Returns:
            List of SandboxInfo
        """
        sandboxes = await self.client.list_sandboxes()

        # Apply filters
        if user_id:
            sandboxes = [
                s for s in sandboxes
                if s.metadata.get("user_id") == user_id
            ]
        if session_id:
            sandboxes = [
                s for s in sandboxes
                if s.metadata.get("session_id") == session_id
            ]

        return sandboxes

    async def cleanup_expired(self) -> int:
        """Cleanup expired sandboxes.
        
        Returns:
            Number of sandboxes cleaned up
        """
        count = await self.client.cleanup_expired()
        
        # Sync local cache
        for sandbox_id in list(self._sandboxes.keys()):
            try:
                info = await self.client.get_status(sandbox_id)
                if info.status in (SandboxStatus.ERROR, SandboxStatus.TIMEOUT):
                    del self._sandboxes[sandbox_id]
            except Exception:
                del self._sandboxes[sandbox_id]

        return count

    async def start_cleanup_task(self, interval: int = 300) -> None:
        """Start background cleanup task.
        
        Args:
            interval: Cleanup interval in seconds
        """
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    count = await self.cleanup_expired()
                    if count > 0:
                        logger.info(f"Cleaned up {count} expired sandboxes")
                except Exception as e:
                    logger.error(f"Cleanup task error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started sandbox cleanup task (interval: {interval}s)")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("Stopped sandbox cleanup task")

    async def shutdown(self) -> None:
        """Shutdown manager and cleanup all sandboxes."""
        await self.stop_cleanup_task()

        # Stop all running sandboxes
        for sandbox_id, info in list(self._sandboxes.items()):
            if info.status == SandboxStatus.RUNNING:
                try:
                    await self.stop_sandbox(sandbox_id)
                except Exception as e:
                    logger.warning(f"Failed to stop sandbox {sandbox_id}: {e}")

        logger.info("Sandbox manager shutdown complete")


def get_sandbox_manager() -> SandboxManager:
    """Get or create the global sandbox manager instance."""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
        logger.info("Sandbox manager initialized")
    return _sandbox_manager


async def cleanup_sandbox_manager() -> None:
    """Cleanup the global sandbox manager."""
    global _sandbox_manager
    if _sandbox_manager:
        await _sandbox_manager.shutdown()
        _sandbox_manager = None
        logger.info("Sandbox manager cleaned up")
