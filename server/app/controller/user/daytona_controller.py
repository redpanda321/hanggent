"""Daytona settings controller for managing per-user Daytona configuration.

Provides endpoints for:
- Saving/updating Daytona API key (encrypted)
- Configuring resource limits (CPU, memory, disk)
- Managing session persistence settings (auto-stop interval)
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.component.auth import Auth, auth_must
from app.component.encrypt import encrypt_credential, decrypt_credential, mask_credential
from app.model.user.daytona_settings import UserDaytonaSettings
from app.model.user.sandbox_session import UserSandboxSession, SandboxStatus

router = APIRouter(prefix="/user/daytona", tags=["daytona"])


# Request/Response Models

class DaytonaSettingsRequest(BaseModel):
    """Request to save Daytona settings."""
    api_key: Optional[str] = Field(
        default=None,
        description="Daytona API key (will be encrypted)"
    )
    server_url: str = Field(
        default="https://app.daytona.io",
        description="Daytona server URL"
    )
    target: str = Field(
        default="us",
        pattern="^(us|eu)$",
        description="Daytona target region: us or eu"
    )
    cpu_limit: int = Field(
        default=2,
        ge=1,
        le=8,
        description="CPU cores (1-8)"
    )
    memory_limit_gb: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Memory in GB (1-16)"
    )
    disk_limit_gb: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Disk in GB (1-50)"
    )
    auto_stop_interval: int = Field(
        default=15,
        ge=5,
        le=120,
        description="Auto-stop after N minutes of inactivity (5-120)"
    )
    auto_archive_interval: int = Field(
        default=1440,
        ge=60,
        le=10080,
        description="Auto-archive after N minutes (60-10080)"
    )
    sandbox_image: Optional[str] = Field(
        default=None,
        description="Custom sandbox image (optional)"
    )
    vnc_password: Optional[str] = Field(
        default=None,
        description="VNC password (optional, auto-generated if not set)"
    )


class DaytonaSettingsResponse(BaseModel):
    """Response with Daytona settings (API key masked)."""
    has_api_key: bool
    api_key_masked: Optional[str] = None
    server_url: str
    target: str
    cpu_limit: int
    memory_limit_gb: int
    disk_limit_gb: int
    auto_stop_interval: int
    auto_archive_interval: int
    sandbox_image: Optional[str] = None
    has_vnc_password: bool = False


class SandboxSessionResponse(BaseModel):
    """Response for a sandbox session."""
    sandbox_id: str
    daytona_sandbox_id: Optional[str] = None
    chat_session_id: Optional[str] = None
    status: str
    vnc_url: Optional[str] = None
    browser_api_url: Optional[str] = None
    workspace_path: str
    last_activity_at: str
    expires_at: Optional[str] = None
    cpu_allocated: Optional[int] = None
    memory_allocated_gb: Optional[int] = None
    error_message: Optional[str] = None


class ApiKeyValidationResponse(BaseModel):
    """Response for API key validation."""
    valid: bool
    error: Optional[str] = None


# Endpoints

@router.get("/settings", response_model=DaytonaSettingsResponse)
async def get_daytona_settings(auth: Auth = Depends(auth_must)):
    """Get current user's Daytona settings.
    
    Returns settings with API key masked for security.
    """
    settings = UserDaytonaSettings.get_by_user_id(auth.id)
    
    if not settings:
        # Return defaults if no settings exist
        return DaytonaSettingsResponse(
            has_api_key=False,
            api_key_masked=None,
            server_url="https://app.daytona.io",
            target="us",
            cpu_limit=2,
            memory_limit_gb=4,
            disk_limit_gb=5,
            auto_stop_interval=15,
            auto_archive_interval=1440,
            sandbox_image=None,
            has_vnc_password=False,
        )
    
    # Mask API key for display
    api_key_masked = None
    if settings.encrypted_api_key:
        try:
            decrypted = decrypt_credential(settings.encrypted_api_key)
            api_key_masked = mask_credential(decrypted)
        except Exception:
            api_key_masked = "***error***"
    
    return DaytonaSettingsResponse(
        has_api_key=bool(settings.encrypted_api_key),
        api_key_masked=api_key_masked,
        server_url=settings.server_url,
        target=settings.target,
        cpu_limit=settings.cpu_limit,
        memory_limit_gb=settings.memory_limit_gb,
        disk_limit_gb=settings.disk_limit_gb,
        auto_stop_interval=settings.auto_stop_interval,
        auto_archive_interval=settings.auto_archive_interval,
        sandbox_image=settings.sandbox_image,
        has_vnc_password=bool(settings.vnc_password),
    )


@router.post("/settings", response_model=DaytonaSettingsResponse)
async def save_daytona_settings(
    request: DaytonaSettingsRequest,
    auth: Auth = Depends(auth_must)
):
    """Save or update Daytona settings for the current user.
    
    API key is encrypted before storage.
    """
    settings = UserDaytonaSettings.get_by_user_id(auth.id)
    
    if not settings:
        settings = UserDaytonaSettings(user_id=auth.id)
    
    # Encrypt API key if provided
    if request.api_key:
        settings.encrypted_api_key = encrypt_credential(request.api_key)
    
    # Update other settings
    settings.server_url = request.server_url
    settings.target = request.target
    settings.cpu_limit = request.cpu_limit
    settings.memory_limit_gb = request.memory_limit_gb
    settings.disk_limit_gb = request.disk_limit_gb
    settings.auto_stop_interval = request.auto_stop_interval
    settings.auto_archive_interval = request.auto_archive_interval
    settings.sandbox_image = request.sandbox_image
    
    if request.vnc_password:
        settings.vnc_password = request.vnc_password
    
    settings.save()
    
    # Return updated settings
    api_key_masked = None
    if settings.encrypted_api_key:
        try:
            decrypted = decrypt_credential(settings.encrypted_api_key)
            api_key_masked = mask_credential(decrypted)
        except Exception:
            api_key_masked = "***error***"
    
    return DaytonaSettingsResponse(
        has_api_key=bool(settings.encrypted_api_key),
        api_key_masked=api_key_masked,
        server_url=settings.server_url,
        target=settings.target,
        cpu_limit=settings.cpu_limit,
        memory_limit_gb=settings.memory_limit_gb,
        disk_limit_gb=settings.disk_limit_gb,
        auto_stop_interval=settings.auto_stop_interval,
        auto_archive_interval=settings.auto_archive_interval,
        sandbox_image=settings.sandbox_image,
        has_vnc_password=bool(settings.vnc_password),
    )


@router.delete("/settings")
async def delete_daytona_settings(auth: Auth = Depends(auth_must)):
    """Delete user's Daytona settings.
    
    This removes the stored API key and resets to defaults.
    """
    settings = UserDaytonaSettings.get_by_user_id(auth.id)
    
    if settings:
        settings.delete()
    
    return {"success": True, "message": "Daytona settings deleted"}


@router.post("/validate-key", response_model=ApiKeyValidationResponse)
async def validate_api_key(
    request: DaytonaSettingsRequest,
    auth: Auth = Depends(auth_must)
):
    """Validate a Daytona API key without saving it.
    
    Tests the key against the Daytona API.
    """
    if not request.api_key:
        return ApiKeyValidationResponse(valid=False, error="API key is required")
    
    try:
        # Import here to avoid circular imports
        from daytona import Daytona, DaytonaConfig
        
        config = DaytonaConfig(
            api_key=request.api_key,
            server_url=request.server_url,
            target=request.target,
        )
        
        # Try to list sandboxes to validate the key
        client = Daytona(config)
        client.list()  # This will fail if key is invalid
        
        return ApiKeyValidationResponse(valid=True)
    except ImportError:
        return ApiKeyValidationResponse(
            valid=False,
            error="Daytona SDK not installed"
        )
    except Exception as e:
        return ApiKeyValidationResponse(
            valid=False,
            error=f"Invalid API key: {str(e)}"
        )


# Sandbox Session Endpoints

@router.get("/sessions", response_model=list[SandboxSessionResponse])
async def list_sandbox_sessions(auth: Auth = Depends(auth_must)):
    """List all sandbox sessions for the current user."""
    sessions = UserSandboxSession.get_active_for_user(auth.id)
    
    return [
        SandboxSessionResponse(
            sandbox_id=s.sandbox_id,
            daytona_sandbox_id=s.daytona_sandbox_id,
            chat_session_id=s.chat_session_id,
            status=s.status,
            vnc_url=s.vnc_url,
            browser_api_url=s.browser_api_url,
            workspace_path=s.workspace_path or "/workspace",
            last_activity_at=s.last_activity_at.isoformat() if s.last_activity_at else "",
            expires_at=s.expires_at.isoformat() if s.expires_at else None,
            cpu_allocated=s.cpu_allocated,
            memory_allocated_gb=s.memory_allocated_gb,
            error_message=s.error_message,
        )
        for s in sessions
    ]


@router.get("/sessions/running", response_model=Optional[SandboxSessionResponse])
async def get_running_session(auth: Auth = Depends(auth_must)):
    """Get current running sandbox session for reuse."""
    session = UserSandboxSession.get_running_for_user(auth.id)
    
    if not session:
        return None
    
    return SandboxSessionResponse(
        sandbox_id=session.sandbox_id,
        daytona_sandbox_id=session.daytona_sandbox_id,
        chat_session_id=session.chat_session_id,
        status=session.status,
        vnc_url=session.vnc_url,
        browser_api_url=session.browser_api_url,
        workspace_path=session.workspace_path or "/workspace",
        last_activity_at=session.last_activity_at.isoformat() if session.last_activity_at else "",
        expires_at=session.expires_at.isoformat() if session.expires_at else None,
        cpu_allocated=session.cpu_allocated,
        memory_allocated_gb=session.memory_allocated_gb,
        error_message=session.error_message,
    )


@router.post("/sessions/{sandbox_id}/touch")
async def touch_session(sandbox_id: str, auth: Auth = Depends(auth_must)):
    """Update session activity timestamp to prevent auto-stop."""
    session = UserSandboxSession.get_by_sandbox_id(sandbox_id)
    
    if not session or session.user_id != auth.id:
        return {"success": False, "error": "Session not found"}
    
    # Get user's auto_stop_interval
    settings = UserDaytonaSettings.get_by_user_id(auth.id)
    auto_stop = settings.auto_stop_interval if settings else 15
    
    session.touch(auto_stop)
    session.save()
    
    return {
        "success": True,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None
    }


@router.delete("/sessions/{sandbox_id}")
async def delete_session(sandbox_id: str, auth: Auth = Depends(auth_must)):
    """Delete a sandbox session record.
    
    Note: This only removes the session record. The actual sandbox
    should be stopped via the sandbox API.
    """
    session = UserSandboxSession.get_by_sandbox_id(sandbox_id)
    
    if not session or session.user_id != auth.id:
        return {"success": False, "error": "Session not found"}
    
    session.status = SandboxStatus.DELETED.value
    session.save()
    
    return {"success": True, "message": "Session deleted"}
