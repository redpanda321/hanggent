"""Daytona cloud sandbox implementation.

Provides isolated browser automation environments using Daytona
cloud sandboxes with built-in VNC streaming support.

Based on patterns from manus/backend-manus sandbox implementation.
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from utils import traceroot_wrapper as traceroot

from app.sandbox.client import (
    BaseSandboxClient,
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)

logger = traceroot.get_logger("sandbox.daytona")

# Daytona SDK with lazy loading
_daytona_client = None


def _get_daytona_client(api_key: str, server_url: str):
    """Get or create Daytona client (lazy initialization)."""
    global _daytona_client
    if _daytona_client is None:
        try:
            from daytona_sdk import Daytona
            _daytona_client = Daytona(
                api_key=api_key,
                server_url=server_url,
            )
            logger.info(f"Daytona client initialized: {server_url}")
        except ImportError:
            logger.error("Daytona SDK not installed. Run: pip install daytona-sdk")
            raise ImportError("Daytona SDK required: pip install daytona-sdk")
        except Exception as e:
            logger.error(f"Failed to connect to Daytona: {e}")
            raise
    return _daytona_client


class DaytonaSandboxClient(BaseSandboxClient):
    """Daytona cloud sandbox client.
    
    Uses Daytona's cloud infrastructure for isolated browser
    automation with VNC streaming.
    
    Features:
    - Resource allocation (CPU, memory, disk)
    - Session persistence with auto_stop_interval
    - VNC browser streaming
    - Session reuse via get_or_start_sandbox()
    """

    DEFAULT_IMAGE = "daytonaio/ai-sandbox:latest"
    VNC_PORT = 6080
    BROWSER_API_PORT = 8003

    def __init__(
        self,
        api_key: str,
        server_url: str = "https://app.daytona.io",
        organization_id: Optional[str] = None,
        target: str = "us",
        cpu_limit: int = 2,
        memory_limit_gb: int = 4,
        disk_limit_gb: int = 5,
        auto_stop_interval: int = 15,
        auto_archive_interval: int = 1440,
        vnc_password: Optional[str] = None,
    ):
        """Initialize Daytona sandbox client.
        
        Args:
            api_key: Daytona API key
            server_url: Daytona server URL
            organization_id: Optional organization ID
            target: Target region (us, eu)
            cpu_limit: CPU cores (1-8)
            memory_limit_gb: Memory in GB (1-16)
            disk_limit_gb: Disk in GB (1-50)
            auto_stop_interval: Minutes of inactivity before auto-stop
            auto_archive_interval: Minutes before auto-archive
            vnc_password: VNC password for browser streaming
        """
        super().__init__()
        self._api_key = api_key
        self._server_url = server_url
        self._organization_id = organization_id
        self._target = target
        self._cpu_limit = cpu_limit
        self._memory_limit_gb = memory_limit_gb
        self._disk_limit_gb = disk_limit_gb
        self._auto_stop_interval = auto_stop_interval
        self._auto_archive_interval = auto_archive_interval
        self._vnc_password = vnc_password or "hanggent"

    @classmethod
    def from_config(cls, config: "DaytonaConfig") -> "DaytonaSandboxClient":
        """Create client from DaytonaConfig.
        
        Args:
            config: DaytonaConfig instance from app.config
            
        Returns:
            Configured DaytonaSandboxClient
        """
        from app.config import DaytonaConfig as ConfigType
        return cls(
            api_key=config.api_key,
            server_url=config.server_url,
            organization_id=config.organization_id,
            target=config.target,
            cpu_limit=config.cpu_limit,
            memory_limit_gb=config.memory_limit_gb,
            disk_limit_gb=config.disk_limit_gb,
            auto_stop_interval=config.auto_stop_interval,
            auto_archive_interval=config.auto_archive_interval,
            vnc_password=config.vnc_password,
        )

    def _get_client(self):
        """Get Daytona client."""
        return _get_daytona_client(self._api_key, self._server_url)

    def _generate_sandbox_id(self) -> str:
        """Generate a unique sandbox ID."""
        return f"hanggent-{uuid.uuid4().hex[:12]}"

    async def get_or_start_sandbox(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> SandboxInfo:
        """Get existing running sandbox or start a stopped one for session reuse.
        
        Implements session persistence pattern from manus - sandboxes stay
        alive between requests and can be reused until auto_stop_interval.
        
        Args:
            user_id: User ID to find sandbox for
            session_id: Optional session ID for more specific matching
            
        Returns:
            SandboxInfo for running sandbox (existing or restarted)
        """
        # Find existing sandbox for user
        for info in self._sandboxes.values():
            metadata = info.metadata or {}
            if metadata.get("user_id") != user_id:
                continue
            if session_id and metadata.get("session_id") != session_id:
                continue
            
            # Found a sandbox for this user
            if info.status == SandboxStatus.RUNNING:
                logger.info(f"Reusing running sandbox: {info.sandbox_id}")
                return info
            
            elif info.status in (SandboxStatus.STOPPED, SandboxStatus.ARCHIVED):
                # Restart the stopped sandbox
                logger.info(f"Restarting stopped sandbox: {info.sandbox_id}")
                return await self.start(info.sandbox_id)
        
        # No existing sandbox, create new one
        logger.info(f"Creating new sandbox for user: {user_id}")
        return await self.create(user_id=user_id, session_id=session_id)

    async def create(
        self,
        config: Optional[SandboxConfig] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> SandboxInfo:
        """Create a new Daytona sandbox.
        
        Args:
            config: Sandbox configuration
            user_id: Optional user ID for labeling
            session_id: Optional session ID for labeling
            
        Returns:
            SandboxInfo with sandbox details
        """
        config = config or SandboxConfig()
        sandbox_id = self._generate_sandbox_id()

        # Create sandbox info in CREATING state
        info = SandboxInfo(
            sandbox_id=sandbox_id,
            status=SandboxStatus.CREATING,
            work_dir=config.work_dir,
            created_at=datetime.utcnow().isoformat(),
            metadata={
                "user_id": user_id,
                "session_id": session_id,
                "image": config.image or self.DEFAULT_IMAGE,
                "target": self._target,
            },
        )
        self._register_sandbox(info)

        try:
            client = self._get_client()

            # Create sandbox parameters
            create_params = {
                "name": sandbox_id,
                "image": config.image or self.DEFAULT_IMAGE,
                "target": self._target,
                "env_vars": {
                    "VNC_PASSWORD": config.vnc_password or "hanggent",
                    "BROWSER_API_PORT": str(self.BROWSER_API_PORT),
                    **config.environment,
                },
                "labels": {
                    "hanggent.sandbox": "true",
                    "hanggent.user_id": user_id or "",
                    "hanggent.session_id": session_id or "",
                    **config.labels,
                },
            }

            if self._organization_id:
                create_params["organization_id"] = self._organization_id

            # Add resource limits using Daytona SDK Resources class
            try:
                from daytona_sdk import Resources
                create_params["resources"] = Resources(
                    cpu=self._cpu_limit,
                    memory=self._memory_limit_gb,
                    disk=self._disk_limit_gb,
                )
            except ImportError:
                # Fallback if Resources not available in SDK version
                logger.warning("Daytona Resources class not available, using defaults")
            
            # Add session persistence settings
            create_params["auto_stop_interval"] = self._auto_stop_interval
            create_params["auto_archive_interval"] = self._auto_archive_interval
            
            # Store resource info in metadata
            info.metadata["cpu_limit"] = self._cpu_limit
            info.metadata["memory_limit_gb"] = self._memory_limit_gb
            info.metadata["disk_limit_gb"] = self._disk_limit_gb
            info.metadata["auto_stop_interval"] = self._auto_stop_interval

            logger.info(
                f"Creating Daytona sandbox: {sandbox_id} "
                f"(cpu={self._cpu_limit}, mem={self._memory_limit_gb}GB, "
                f"auto_stop={self._auto_stop_interval}min)"
            )
            
            # Create sandbox using Daytona SDK
            # Note: Actual API calls depend on Daytona SDK version
            sandbox = await asyncio.to_thread(
                client.sandbox.create,
                **create_params,
            )

            # Get sandbox URLs
            daytona_id = sandbox.id if hasattr(sandbox, "id") else sandbox_id
            info.metadata["daytona_id"] = daytona_id

            # Wait for sandbox to be ready and get URLs
            info.status = SandboxStatus.STARTING
            self._register_sandbox(info)

            await self._wait_for_ready(client, daytona_id, info, timeout=120)

            logger.info(f"Daytona sandbox ready: {sandbox_id}")
            return info

        except Exception as e:
            logger.error(f"Failed to create Daytona sandbox: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            self._register_sandbox(info)
            raise

    async def _wait_for_ready(
        self,
        client,
        daytona_id: str,
        info: SandboxInfo,
        timeout: int = 120,
    ) -> bool:
        """Wait for Daytona sandbox to be ready."""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                # Get sandbox status from Daytona
                sandbox = await asyncio.to_thread(
                    client.sandbox.get,
                    daytona_id,
                )

                status = getattr(sandbox, "status", "unknown")
                if status == "running":
                    # Get URLs from sandbox info
                    if hasattr(sandbox, "get_preview_link"):
                        vnc_url = sandbox.get_preview_link(self.VNC_PORT)
                        api_url = sandbox.get_preview_link(self.BROWSER_API_PORT)
                        info.vnc_url = vnc_url
                        info.browser_api_url = api_url
                    elif hasattr(sandbox, "urls"):
                        info.vnc_url = sandbox.urls.get("vnc")
                        info.browser_api_url = sandbox.urls.get("browser_api")

                    info.status = SandboxStatus.RUNNING
                    self._register_sandbox(info)
                    return True

                elif status in ("failed", "error"):
                    info.status = SandboxStatus.ERROR
                    info.error_message = getattr(sandbox, "error", "Unknown error")
                    self._register_sandbox(info)
                    return False

            except Exception as e:
                logger.warning(f"Error checking sandbox status: {e}")

            await asyncio.sleep(3)

        logger.warning(f"Sandbox {info.sandbox_id} did not become ready in {timeout}s")
        info.status = SandboxStatus.TIMEOUT
        info.error_message = f"Sandbox did not start within {timeout} seconds"
        self._register_sandbox(info)
        return False

    async def start(self, sandbox_id: str) -> SandboxInfo:
        """Start a stopped Daytona sandbox."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        daytona_id = info.metadata.get("daytona_id")
        if not daytona_id:
            raise ValueError(f"Daytona ID not found for sandbox: {sandbox_id}")

        try:
            client = self._get_client()
            await asyncio.to_thread(client.sandbox.start, daytona_id)

            info.status = SandboxStatus.STARTING
            self._register_sandbox(info)

            await self._wait_for_ready(client, daytona_id, info)
            return info

        except Exception as e:
            logger.error(f"Failed to start Daytona sandbox {sandbox_id}: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            self._register_sandbox(info)
            raise

    async def stop(self, sandbox_id: str) -> SandboxInfo:
        """Stop a running Daytona sandbox."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        daytona_id = info.metadata.get("daytona_id")
        if not daytona_id:
            raise ValueError(f"Daytona ID not found for sandbox: {sandbox_id}")

        try:
            client = self._get_client()
            await asyncio.to_thread(client.sandbox.stop, daytona_id)

            info.status = SandboxStatus.STOPPED
            self._register_sandbox(info)
            logger.info(f"Stopped Daytona sandbox: {sandbox_id}")
            return info

        except Exception as e:
            logger.error(f"Failed to stop Daytona sandbox {sandbox_id}: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            raise

    async def remove(self, sandbox_id: str) -> bool:
        """Remove a Daytona sandbox completely."""
        info = self._get_cached_sandbox(sandbox_id)
        daytona_id = info.metadata.get("daytona_id") if info else None

        try:
            if daytona_id:
                client = self._get_client()
                await asyncio.to_thread(client.sandbox.delete, daytona_id)

            self._unregister_sandbox(sandbox_id)
            logger.info(f"Removed Daytona sandbox: {sandbox_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove Daytona sandbox {sandbox_id}: {e}")
            return False

    async def get_status(self, sandbox_id: str) -> SandboxInfo:
        """Get current status of a Daytona sandbox."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        daytona_id = info.metadata.get("daytona_id")
        if not daytona_id:
            return info

        try:
            client = self._get_client()
            sandbox = await asyncio.to_thread(client.sandbox.get, daytona_id)

            # Map Daytona status to our status
            daytona_status = getattr(sandbox, "status", "unknown")
            status_map = {
                "creating": SandboxStatus.CREATING,
                "starting": SandboxStatus.STARTING,
                "running": SandboxStatus.RUNNING,
                "stopping": SandboxStatus.STOPPING,
                "stopped": SandboxStatus.STOPPED,
                "failed": SandboxStatus.ERROR,
                "error": SandboxStatus.ERROR,
            }
            info.status = status_map.get(daytona_status, SandboxStatus.ERROR)

            # Update URLs if available
            if hasattr(sandbox, "get_preview_link"):
                info.vnc_url = sandbox.get_preview_link(self.VNC_PORT)
                info.browser_api_url = sandbox.get_preview_link(self.BROWSER_API_PORT)

            self._register_sandbox(info)
            return info

        except Exception as e:
            logger.error(f"Failed to get status for Daytona sandbox {sandbox_id}: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            return info

    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Execute a command inside the Daytona sandbox."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        daytona_id = info.metadata.get("daytona_id")
        if not daytona_id:
            raise ValueError(f"Daytona ID not found for sandbox: {sandbox_id}")

        try:
            client = self._get_client()
            
            # Execute command using Daytona SDK
            result = await asyncio.to_thread(
                client.sandbox.exec,
                daytona_id,
                command,
                timeout=timeout,
            )

            return {
                "stdout": getattr(result, "stdout", ""),
                "stderr": getattr(result, "stderr", ""),
                "exit_code": getattr(result, "exit_code", 0),
            }

        except Exception as e:
            logger.error(f"Failed to execute command in Daytona sandbox {sandbox_id}: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
            }

    async def upload_file(
        self,
        sandbox_id: str,
        local_path: str,
        remote_path: str,
    ) -> bool:
        """Upload a file to the Daytona sandbox."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        daytona_id = info.metadata.get("daytona_id")
        if not daytona_id:
            raise ValueError(f"Daytona ID not found for sandbox: {sandbox_id}")

        try:
            client = self._get_client()

            # Upload using Daytona SDK file system API
            with open(local_path, "rb") as f:
                content = f.read()

            await asyncio.to_thread(
                client.sandbox.fs.write,
                daytona_id,
                remote_path,
                content,
            )

            logger.debug(f"Uploaded {local_path} to Daytona {sandbox_id}:{remote_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload file to Daytona sandbox {sandbox_id}: {e}")
            return False

    async def download_file(
        self,
        sandbox_id: str,
        remote_path: str,
        local_path: str,
    ) -> bool:
        """Download a file from the Daytona sandbox."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        daytona_id = info.metadata.get("daytona_id")
        if not daytona_id:
            raise ValueError(f"Daytona ID not found for sandbox: {sandbox_id}")

        try:
            client = self._get_client()

            # Download using Daytona SDK file system API
            content = await asyncio.to_thread(
                client.sandbox.fs.read,
                daytona_id,
                remote_path,
            )

            # Write to local file
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                if isinstance(content, str):
                    f.write(content.encode("utf-8"))
                else:
                    f.write(content)

            logger.debug(f"Downloaded Daytona {sandbox_id}:{remote_path} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to download file from Daytona sandbox {sandbox_id}: {e}")
            return False

    async def list_sandboxes(self) -> list[SandboxInfo]:
        """List all Hanggent sandboxes in Daytona."""
        try:
            client = self._get_client()
            sandboxes = await asyncio.to_thread(client.sandbox.list)

            result = []
            for sandbox in sandboxes:
                # Filter for Hanggent sandboxes
                labels = getattr(sandbox, "labels", {})
                if labels.get("hanggent.sandbox") == "true":
                    sandbox_id = labels.get("hanggent.sandbox.id") or sandbox.name
                    info = self._get_cached_sandbox(sandbox_id)
                    if info:
                        result.append(info)
                    else:
                        # Reconstruct info
                        result.append(SandboxInfo(
                            sandbox_id=sandbox_id,
                            status=SandboxStatus.RUNNING if sandbox.status == "running" else SandboxStatus.STOPPED,
                            metadata={
                                "daytona_id": sandbox.id,
                                "user_id": labels.get("hanggent.user_id", ""),
                                "session_id": labels.get("hanggent.session_id", ""),
                            },
                        ))

            return result

        except Exception as e:
            logger.error(f"Failed to list Daytona sandboxes: {e}")
            return list(self._sandboxes.values())

    async def cleanup_expired(self) -> int:
        """Cleanup expired Daytona sandboxes."""
        # Daytona has its own cleanup policies
        # This method can be used to sync local cache
        count = 0
        try:
            sandboxes = await self.list_sandboxes()
            
            for info in sandboxes:
                if info.status == SandboxStatus.STOPPED:
                    await self.remove(info.sandbox_id)
                    count += 1

            logger.info(f"Cleaned up {count} expired Daytona sandboxes")

        except Exception as e:
            logger.error(f"Failed to cleanup Daytona sandboxes: {e}")

        return count
