"""Sandbox API controller for managing isolated browser environments.

Provides REST API endpoints for creating, managing, and monitoring
sandbox environments with VNC streaming support.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from utils import traceroot_wrapper as traceroot

from app.config import SandboxType, get_config
from app.sandbox.client import SandboxConfig, SandboxInfo, SandboxStatus
from app.sandbox.manager import get_sandbox_manager

logger = traceroot.get_logger("sandbox_controller")

router = APIRouter(prefix="/sandbox", tags=["Sandbox"])


# Request/Response Models
class CreateSandboxRequest(BaseModel):
    """Request to create a new sandbox."""
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for workspace isolation"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for workspace isolation"
    )
    image: Optional[str] = Field(
        default=None,
        description="Custom container image"
    )
    memory_limit: Optional[str] = Field(
        default=None,
        description="Memory limit (e.g., '512m', '1g')"
    )
    cpu_limit: Optional[float] = Field(
        default=None,
        description="CPU limit (e.g., 1.0, 2.0)"
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Sandbox timeout in seconds"
    )
    vnc_enabled: Optional[bool] = Field(
        default=True,
        description="Enable VNC streaming"
    )
    vnc_password: Optional[str] = Field(
        default=None,
        description="Custom VNC password"
    )


class SandboxResponse(BaseModel):
    """Sandbox information response."""
    sandbox_id: str
    status: str
    vnc_url: Optional[str] = None
    browser_api_url: Optional[str] = None
    work_dir: str = "/workspace"
    created_at: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict = {}

    @classmethod
    def from_info(cls, info: SandboxInfo) -> "SandboxResponse":
        """Create response from SandboxInfo."""
        return cls(
            sandbox_id=info.sandbox_id,
            status=info.status.value,
            vnc_url=info.vnc_url,
            browser_api_url=info.browser_api_url,
            work_dir=info.work_dir,
            created_at=info.created_at,
            error_message=info.error_message,
            metadata=info.metadata,
        )


class VncUrlResponse(BaseModel):
    """VNC URL response."""
    sandbox_id: str
    vnc_url: Optional[str]
    status: str


class CommandRequest(BaseModel):
    """Request to execute a command."""
    command: str = Field(..., description="Command to execute")
    timeout: int = Field(default=60, description="Execution timeout in seconds")


class CommandResponse(BaseModel):
    """Command execution response."""
    stdout: str
    stderr: str
    exit_code: int


class SandboxListResponse(BaseModel):
    """List of sandboxes response."""
    sandboxes: list[SandboxResponse]
    total: int


class SandboxStatusResponse(BaseModel):
    """Sandbox status check response."""
    enabled: bool
    sandbox_type: str
    configured: bool
    message: str


# Endpoints
@router.get("/status", response_model=SandboxStatusResponse)
async def get_sandbox_status():
    """Check if sandbox functionality is enabled and configured."""
    config = get_config()
    sandbox_type = config.sandbox.sandbox_type

    if sandbox_type == SandboxType.NONE:
        return SandboxStatusResponse(
            enabled=False,
            sandbox_type="none",
            configured=False,
            message="Sandbox is not enabled. Set HANGGENT_SANDBOX__SANDBOX_TYPE to 'docker' or 'daytona'.",
        )

    if sandbox_type == SandboxType.DAYTONA and not config.daytona.is_configured:
        return SandboxStatusResponse(
            enabled=True,
            sandbox_type="daytona",
            configured=False,
            message="Daytona sandbox requires HANGGENT_DAYTONA__API_KEY to be set.",
        )

    return SandboxStatusResponse(
        enabled=True,
        sandbox_type=sandbox_type.value,
        configured=True,
        message=f"Sandbox is enabled using {sandbox_type.value}.",
    )


@router.post("/create", response_model=SandboxResponse, status_code=status.HTTP_201_CREATED)
async def create_sandbox(request: CreateSandboxRequest):
    """Create a new sandbox environment.
    
    Creates an isolated browser automation environment with optional
    VNC streaming for visual monitoring.
    """
    manager = get_sandbox_manager()

    if not manager.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sandbox functionality is not enabled. Configure HANGGENT_SANDBOX__SANDBOX_TYPE.",
        )

    try:
        # Build custom config if any options provided
        custom_config = None
        if any([
            request.image,
            request.memory_limit,
            request.cpu_limit,
            request.timeout,
            request.vnc_password,
            request.vnc_enabled is not None,
        ]):
            app_config = get_config()
            custom_config = SandboxConfig(
                image=request.image or app_config.sandbox.image,
                memory_limit=request.memory_limit or app_config.sandbox.memory_limit,
                cpu_limit=request.cpu_limit or app_config.sandbox.cpu_limit,
                timeout=request.timeout or app_config.sandbox.timeout,
                vnc_enabled=request.vnc_enabled if request.vnc_enabled is not None else app_config.sandbox.vnc_enabled,
                vnc_password=request.vnc_password or app_config.sandbox.vnc_password,
            )

        info = await manager.create_sandbox(
            user_id=request.user_id,
            session_id=request.session_id,
            config=custom_config,
        )

        logger.info(f"Created sandbox: {info.sandbox_id}")
        return SandboxResponse.from_info(info)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create sandbox: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sandbox: {str(e)}",
        )


@router.get("/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(sandbox_id: str):
    """Get sandbox information by ID."""
    manager = get_sandbox_manager()

    try:
        info = await manager.get_sandbox(sandbox_id)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sandbox not found: {sandbox_id}",
            )
        return SandboxResponse.from_info(info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sandbox {sandbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{sandbox_id}/vnc-url", response_model=VncUrlResponse)
async def get_vnc_url(sandbox_id: str):
    """Get VNC streaming URL for a sandbox.
    
    Returns the noVNC websocket URL for browser display streaming.
    """
    manager = get_sandbox_manager()

    try:
        info = await manager.get_sandbox(sandbox_id)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sandbox not found: {sandbox_id}",
            )

        vnc_url = await manager.get_vnc_url(sandbox_id)

        return VncUrlResponse(
            sandbox_id=sandbox_id,
            vnc_url=vnc_url,
            status=info.status.value,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get VNC URL for {sandbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{sandbox_id}/start", response_model=SandboxResponse)
async def start_sandbox(sandbox_id: str):
    """Start a stopped sandbox."""
    manager = get_sandbox_manager()

    try:
        info = await manager.start_sandbox(sandbox_id)
        return SandboxResponse.from_info(info)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to start sandbox {sandbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{sandbox_id}/stop", response_model=SandboxResponse)
async def stop_sandbox(sandbox_id: str):
    """Stop a running sandbox."""
    manager = get_sandbox_manager()

    try:
        info = await manager.stop_sandbox(sandbox_id)
        return SandboxResponse.from_info(info)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to stop sandbox {sandbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_sandbox(sandbox_id: str):
    """Remove a sandbox completely."""
    manager = get_sandbox_manager()

    try:
        success = await manager.remove_sandbox(sandbox_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove sandbox: {sandbox_id}",
            )

    except Exception as e:
        logger.error(f"Failed to remove sandbox {sandbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{sandbox_id}/exec", response_model=CommandResponse)
async def execute_command(sandbox_id: str, request: CommandRequest):
    """Execute a command inside the sandbox."""
    manager = get_sandbox_manager()

    try:
        result = await manager.execute_command(
            sandbox_id=sandbox_id,
            command=request.command,
            timeout=request.timeout,
        )
        return CommandResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to execute command in {sandbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/", response_model=SandboxListResponse)
async def list_sandboxes(
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    session_id: Optional[str] = Query(default=None, description="Filter by session ID"),
):
    """List all sandboxes, optionally filtered by user or session."""
    manager = get_sandbox_manager()

    if not manager.is_enabled:
        return SandboxListResponse(sandboxes=[], total=0)

    try:
        sandboxes = await manager.list_sandboxes(
            user_id=user_id,
            session_id=session_id,
        )
        
        return SandboxListResponse(
            sandboxes=[SandboxResponse.from_info(s) for s in sandboxes],
            total=len(sandboxes),
        )

    except Exception as e:
        logger.error(f"Failed to list sandboxes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# File Sync Models
class FileSyncRequest(BaseModel):
    """Request to sync files to sandbox."""
    workspace_path: str = Field(
        ...,
        description="Local workspace directory path"
    )
    file_paths: Optional[list[str]] = Field(
        default=None,
        description="Specific files to sync (relative paths). If empty, syncs all files."
    )
    remote_base_path: str = Field(
        default="/workspace",
        description="Base path inside sandbox"
    )


class FileSyncResultItem(BaseModel):
    """Result of a single file sync."""
    filename: str
    local_path: str
    remote_path: str
    size: int
    success: bool
    error: Optional[str] = None
    synced_at: Optional[str] = None


class FileSyncResponse(BaseModel):
    """File sync operation response."""
    total_files: int
    synced_files: int
    failed_files: int
    total_bytes: int
    synced_bytes: int
    success_rate: float
    started_at: str
    completed_at: str
    results: list[FileSyncResultItem]


@router.post("/{sandbox_id}/sync-files", response_model=FileSyncResponse)
async def sync_files_to_sandbox(sandbox_id: str, request: FileSyncRequest):
    """Sync workspace files to sandbox on demand.
    
    Syncs files from local workspace to the sandbox environment.
    Use file_paths to sync specific files, or leave empty to sync all.
    
    Excludes common patterns like __pycache__, .git, node_modules, etc.
    """
    manager = get_sandbox_manager()

    if not manager.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sandbox is not enabled",
        )

    # Verify sandbox exists
    try:
        info = await manager.get_sandbox(sandbox_id)
        if info.status != SandboxStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sandbox is not running (status: {info.status.value})",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    try:
        from app.service.file_sync import get_file_sync_service

        # Get file sync service
        sync_service = get_file_sync_service(manager._client)
        
        # Sync files
        summary = await sync_service.sync_workspace_to_sandbox(
            sandbox_id=sandbox_id,
            workspace_path=request.workspace_path,
            remote_base_path=request.remote_base_path,
            file_paths=request.file_paths,
        )
        
        return FileSyncResponse(
            total_files=summary.total_files,
            synced_files=summary.synced_files,
            failed_files=summary.failed_files,
            total_bytes=summary.total_bytes,
            synced_bytes=summary.synced_bytes,
            success_rate=summary.success_rate,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
            results=[
                FileSyncResultItem(
                    filename=r.filename,
                    local_path=r.local_path,
                    remote_path=r.remote_path,
                    size=r.size,
                    success=r.success,
                    error=r.error,
                    synced_at=r.synced_at,
                )
                for r in summary.results
            ],
        )

    except Exception as e:
        logger.error(f"Failed to sync files to sandbox {sandbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_sandboxes():
    """Cleanup expired sandboxes.
    
    Removes sandboxes that have exceeded their timeout or are in error state.
    """
    manager = get_sandbox_manager()

    if not manager.is_enabled:
        return {"cleaned": 0, "message": "Sandbox not enabled"}

    try:
        count = await manager.cleanup_expired()
        return {"cleaned": count, "message": f"Cleaned up {count} sandbox(es)"}

    except Exception as e:
        logger.error(f"Failed to cleanup sandboxes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
