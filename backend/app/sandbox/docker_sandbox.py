"""Docker-based sandbox implementation.

Provides isolated browser automation environments using Docker
containers with noVNC for browser streaming.
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

logger = traceroot.get_logger("sandbox.docker")

# Docker import with lazy loading
_docker_client = None


def _get_docker_client():
    """Get or create Docker client (lazy initialization)."""
    global _docker_client
    if _docker_client is None:
        try:
            import docker
            _docker_client = docker.from_env()
            logger.info("Docker client initialized")
        except ImportError:
            logger.error("Docker SDK not installed. Run: pip install docker")
            raise ImportError("Docker SDK required: pip install docker")
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise
    return _docker_client


class DockerSandboxClient(BaseSandboxClient):
    """Docker-based sandbox client for local isolated environments.
    
    Uses Docker containers with browser_use and noVNC for browser
    automation with visual streaming.
    """

    CONTAINER_PREFIX = "hanggent-sandbox-"
    DEFAULT_IMAGE = "ghcr.io/browser-use/browser-use:latest"

    def __init__(self, host_vnc_port_start: int = 6080, host_api_port_start: int = 8003):
        """Initialize Docker sandbox client.
        
        Args:
            host_vnc_port_start: Starting port for VNC mapping
            host_api_port_start: Starting port for browser API mapping
        """
        super().__init__()
        self._host_vnc_port = host_vnc_port_start
        self._host_api_port = host_api_port_start
        self._port_map: Dict[str, Dict[str, int]] = {}

    def _allocate_ports(self, sandbox_id: str) -> Dict[str, int]:
        """Allocate host ports for a sandbox."""
        ports = {
            "vnc": self._host_vnc_port,
            "api": self._host_api_port,
        }
        self._port_map[sandbox_id] = ports
        self._host_vnc_port += 1
        self._host_api_port += 1
        return ports

    def _release_ports(self, sandbox_id: str) -> None:
        """Release ports for a sandbox."""
        if sandbox_id in self._port_map:
            del self._port_map[sandbox_id]

    def _generate_sandbox_id(self) -> str:
        """Generate a unique sandbox ID."""
        return f"{self.CONTAINER_PREFIX}{uuid.uuid4().hex[:12]}"

    def _get_container_name(self, sandbox_id: str) -> str:
        """Get container name from sandbox ID."""
        return sandbox_id

    async def create(
        self,
        config: Optional[SandboxConfig] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> SandboxInfo:
        """Create a new Docker sandbox container.
        
        Args:
            config: Sandbox configuration
            user_id: Optional user ID for labeling
            session_id: Optional session ID for labeling
            
        Returns:
            SandboxInfo with container details
        """
        config = config or SandboxConfig()
        sandbox_id = self._generate_sandbox_id()
        container_name = self._get_container_name(sandbox_id)

        # Create sandbox info in CREATING state
        info = SandboxInfo(
            sandbox_id=sandbox_id,
            status=SandboxStatus.CREATING,
            work_dir=config.work_dir,
            created_at=datetime.utcnow().isoformat(),
            metadata={
                "user_id": user_id,
                "session_id": session_id,
                "image": config.image,
            },
        )
        self._register_sandbox(info)

        try:
            client = _get_docker_client()

            # Allocate ports
            ports = self._allocate_ports(sandbox_id)

            # Prepare environment variables
            environment = {
                "DISPLAY": ":99",
                "VNC_PASSWORD": config.vnc_password or "hanggent",
                "BROWSER_API_PORT": str(config.browser_api_port),
                **config.environment,
            }

            # Prepare labels
            labels = {
                "hanggent.sandbox": "true",
                "hanggent.sandbox.id": sandbox_id,
                "hanggent.sandbox.user_id": user_id or "",
                "hanggent.sandbox.session_id": session_id or "",
                **config.labels,
            }

            # Port bindings
            port_bindings = {}
            if config.vnc_enabled:
                port_bindings[f"{config.vnc_port}/tcp"] = ports["vnc"]
            port_bindings[f"{config.browser_api_port}/tcp"] = ports["api"]

            # Resource limits
            mem_limit = config.memory_limit
            cpu_period = 100000
            cpu_quota = int(config.cpu_limit * cpu_period)

            # Create container
            logger.info(f"Creating Docker container: {container_name}")
            container = client.containers.create(
                image=config.image or self.DEFAULT_IMAGE,
                name=container_name,
                environment=environment,
                labels=labels,
                ports=port_bindings,
                mem_limit=mem_limit,
                cpu_period=cpu_period,
                cpu_quota=cpu_quota,
                network_mode="bridge" if config.network_enabled else "none",
                detach=True,
                tty=True,
            )

            # Update info with URLs
            host = os.environ.get("SANDBOX_HOST", "localhost")
            info.vnc_url = f"ws://{host}:{ports['vnc']}" if config.vnc_enabled else None
            info.browser_api_url = f"http://{host}:{ports['api']}"
            info.metadata["container_id"] = container.id

            # Start the container
            logger.info(f"Starting container: {container_name}")
            container.start()

            # Wait for container to be ready
            info.status = SandboxStatus.STARTING
            self._register_sandbox(info)

            # Wait for browser API to be available
            await self._wait_for_ready(info, timeout=60)

            info.status = SandboxStatus.RUNNING
            self._register_sandbox(info)
            logger.info(f"Sandbox ready: {sandbox_id}")

            return info

        except Exception as e:
            logger.error(f"Failed to create sandbox: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            self._register_sandbox(info)
            raise

    async def _wait_for_ready(self, info: SandboxInfo, timeout: int = 60) -> bool:
        """Wait for sandbox to be ready (browser API responding)."""
        import aiohttp

        if not info.browser_api_url:
            return False

        health_url = f"{info.browser_api_url}/health"
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_url, timeout=5) as response:
                        if response.status == 200:
                            logger.debug(f"Sandbox {info.sandbox_id} is ready")
                            return True
            except Exception:
                pass
            await asyncio.sleep(2)

        logger.warning(f"Sandbox {info.sandbox_id} did not become ready in {timeout}s")
        return False

    async def start(self, sandbox_id: str) -> SandboxInfo:
        """Start a stopped container."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        try:
            client = _get_docker_client()
            container = client.containers.get(self._get_container_name(sandbox_id))
            container.start()

            info.status = SandboxStatus.STARTING
            self._register_sandbox(info)

            await self._wait_for_ready(info)

            info.status = SandboxStatus.RUNNING
            self._register_sandbox(info)
            return info

        except Exception as e:
            logger.error(f"Failed to start sandbox {sandbox_id}: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            self._register_sandbox(info)
            raise

    async def stop(self, sandbox_id: str) -> SandboxInfo:
        """Stop a running container."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        try:
            client = _get_docker_client()
            container = client.containers.get(self._get_container_name(sandbox_id))
            container.stop(timeout=10)

            info.status = SandboxStatus.STOPPED
            self._register_sandbox(info)
            logger.info(f"Stopped sandbox: {sandbox_id}")
            return info

        except Exception as e:
            logger.error(f"Failed to stop sandbox {sandbox_id}: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            raise

    async def remove(self, sandbox_id: str) -> bool:
        """Remove a container completely."""
        try:
            client = _get_docker_client()
            container_name = self._get_container_name(sandbox_id)
            
            try:
                container = client.containers.get(container_name)
                container.remove(force=True)
            except Exception:
                pass  # Container might not exist

            self._release_ports(sandbox_id)
            self._unregister_sandbox(sandbox_id)
            logger.info(f"Removed sandbox: {sandbox_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove sandbox {sandbox_id}: {e}")
            return False

    async def get_status(self, sandbox_id: str) -> SandboxInfo:
        """Get current status of a container."""
        info = self._get_cached_sandbox(sandbox_id)
        if not info:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        try:
            client = _get_docker_client()
            container = client.containers.get(self._get_container_name(sandbox_id))
            container.reload()

            # Map Docker status to our status
            docker_status = container.status
            if docker_status == "running":
                info.status = SandboxStatus.RUNNING
            elif docker_status == "exited":
                info.status = SandboxStatus.STOPPED
            elif docker_status in ("created", "restarting"):
                info.status = SandboxStatus.STARTING
            else:
                info.status = SandboxStatus.ERROR

            self._register_sandbox(info)
            return info

        except Exception as e:
            logger.error(f"Failed to get status for {sandbox_id}: {e}")
            info.status = SandboxStatus.ERROR
            info.error_message = str(e)
            return info

    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Execute a command inside the container."""
        try:
            client = _get_docker_client()
            container = client.containers.get(self._get_container_name(sandbox_id))
            
            result = container.exec_run(
                cmd=["bash", "-c", command],
                demux=True,
                timeout=timeout,
            )

            stdout, stderr = result.output
            return {
                "stdout": stdout.decode("utf-8") if stdout else "",
                "stderr": stderr.decode("utf-8") if stderr else "",
                "exit_code": result.exit_code,
            }

        except Exception as e:
            logger.error(f"Failed to execute command in {sandbox_id}: {e}")
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
        """Upload a file to the container."""
        import tarfile
        import io

        try:
            client = _get_docker_client()
            container = client.containers.get(self._get_container_name(sandbox_id))

            # Create tar archive
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tar.add(local_path, arcname=os.path.basename(remote_path))
            tar_stream.seek(0)

            # Upload to container
            remote_dir = os.path.dirname(remote_path)
            container.put_archive(remote_dir or "/", tar_stream)

            logger.debug(f"Uploaded {local_path} to {sandbox_id}:{remote_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload file to {sandbox_id}: {e}")
            return False

    async def download_file(
        self,
        sandbox_id: str,
        remote_path: str,
        local_path: str,
    ) -> bool:
        """Download a file from the container."""
        import tarfile
        import io

        try:
            client = _get_docker_client()
            container = client.containers.get(self._get_container_name(sandbox_id))

            # Get file as tar archive
            bits, stat = container.get_archive(remote_path)

            # Extract file
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)

            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                member = tar.getmembers()[0]
                member.name = os.path.basename(local_path)
                tar.extract(member, path=os.path.dirname(local_path) or ".")

            logger.debug(f"Downloaded {sandbox_id}:{remote_path} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to download file from {sandbox_id}: {e}")
            return False

    async def list_sandboxes(self) -> list[SandboxInfo]:
        """List all Hanggent sandbox containers."""
        try:
            client = _get_docker_client()
            containers = client.containers.list(
                all=True,
                filters={"label": "hanggent.sandbox=true"},
            )

            sandboxes = []
            for container in containers:
                sandbox_id = container.labels.get("hanggent.sandbox.id")
                if sandbox_id:
                    info = self._get_cached_sandbox(sandbox_id)
                    if info:
                        sandboxes.append(info)
                    else:
                        # Reconstruct info from container
                        sandboxes.append(SandboxInfo(
                            sandbox_id=sandbox_id,
                            status=SandboxStatus.RUNNING if container.status == "running" else SandboxStatus.STOPPED,
                            metadata={
                                "container_id": container.id,
                                "user_id": container.labels.get("hanggent.sandbox.user_id", ""),
                                "session_id": container.labels.get("hanggent.sandbox.session_id", ""),
                            },
                        ))

            return sandboxes

        except Exception as e:
            logger.error(f"Failed to list sandboxes: {e}")
            return list(self._sandboxes.values())

    async def cleanup_expired(self) -> int:
        """Cleanup expired sandbox containers."""
        # For Docker, we rely on timeout labels or external cleanup
        # This method can be extended to check container age
        count = 0
        try:
            client = _get_docker_client()
            containers = client.containers.list(
                all=True,
                filters={"label": "hanggent.sandbox=true"},
            )

            for container in containers:
                # Check if container has been stopped for too long
                if container.status == "exited":
                    sandbox_id = container.labels.get("hanggent.sandbox.id")
                    if sandbox_id:
                        await self.remove(sandbox_id)
                        count += 1

            logger.info(f"Cleaned up {count} expired sandboxes")

        except Exception as e:
            logger.error(f"Failed to cleanup sandboxes: {e}")

        return count
