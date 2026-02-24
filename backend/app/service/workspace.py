"""Workspace manager for per-user/session directory isolation.

Provides workspace creation, management, and cleanup with isolation
policies for multi-tenant operation.
"""

import asyncio
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import aiofiles
import aiofiles.os

from app.config import get_config
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("workspace")


@dataclass
class WorkspaceInfo:
    """Information about a workspace."""
    workspace_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    path: str
    created_at: datetime
    last_accessed: datetime
    size_bytes: int = 0
    file_count: int = 0
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "path": self.path,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
            "metadata": self.metadata,
        }


class WorkspaceManager:
    """Manages workspaces with user/session isolation.
    
    Supports:
    - Per-user workspace isolation
    - Per-session workspace isolation
    - Automatic cleanup of old workspaces
    - Workspace size tracking
    - Concurrent workspace limits
    """

    def __init__(self):
        """Initialize workspace manager."""
        self._config = get_config()
        self._workspaces: Dict[str, WorkspaceInfo] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._ensure_base_directory()

    def _ensure_base_directory(self) -> None:
        """Ensure base workspace directory exists."""
        base_path = os.path.expanduser(self._config.workspace.base_path)
        os.makedirs(base_path, exist_ok=True)

    def _generate_workspace_id(self) -> str:
        """Generate unique workspace ID."""
        return f"ws-{uuid.uuid4().hex[:12]}"

    def _get_workspace_path(
        self,
        workspace_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Get path for a workspace.
        
        Args:
            workspace_id: Workspace ID
            user_id: Optional user ID for organization
            session_id: Optional session ID for organization
            
        Returns:
            Full path to workspace directory
        """
        base = os.path.expanduser(self._config.workspace.base_path)
        
        # Organize by user if available
        if user_id:
            base = os.path.join(base, f"user_{user_id}")
        
        return os.path.join(base, workspace_id)

    async def _calculate_workspace_size(self, path: str) -> tuple[int, int]:
        """Calculate total size and file count of workspace.
        
        Args:
            path: Workspace directory path
            
        Returns:
            Tuple of (size_bytes, file_count)
        """
        total_size = 0
        file_count = 0
        
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(fp)
                        file_count += 1
                    except OSError:
                        pass
        except Exception as e:
            logger.error(f"Error calculating workspace size: {e}")
        
        return total_size, file_count

    async def create_workspace(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> WorkspaceInfo:
        """Create a new workspace.
        
        Args:
            user_id: User ID for isolation
            session_id: Session ID for isolation
            metadata: Optional metadata
            
        Returns:
            WorkspaceInfo for created workspace
            
        Raises:
            ValueError: If workspace limits exceeded
        """
        # Check workspace limits
        if user_id:
            user_workspaces = [
                w for w in self._workspaces.values()
                if w.user_id == user_id
            ]
            if len(user_workspaces) >= self._config.workspace.max_workspaces_per_user:
                raise ValueError(
                    f"Maximum workspaces ({self._config.workspace.max_workspaces_per_user}) "
                    f"reached for user {user_id}"
                )

        workspace_id = self._generate_workspace_id()
        path = self._get_workspace_path(workspace_id, user_id, session_id)
        
        # Create directory
        os.makedirs(path, exist_ok=True)
        
        now = datetime.utcnow()
        workspace = WorkspaceInfo(
            workspace_id=workspace_id,
            user_id=user_id,
            session_id=session_id,
            path=path,
            created_at=now,
            last_accessed=now,
            metadata=metadata or {},
        )
        
        self._workspaces[workspace_id] = workspace
        logger.info(f"Created workspace: {workspace_id}", extra={"user_id": user_id})
        
        return workspace

    async def get_workspace(
        self,
        workspace_id: str,
        update_access: bool = True,
    ) -> Optional[WorkspaceInfo]:
        """Get workspace by ID.
        
        Args:
            workspace_id: Workspace ID
            update_access: Update last accessed time
            
        Returns:
            WorkspaceInfo or None if not found
        """
        workspace = self._workspaces.get(workspace_id)
        
        if workspace:
            if update_access:
                workspace.last_accessed = datetime.utcnow()
            
            # Update size and file count
            workspace.size_bytes, workspace.file_count = \
                await self._calculate_workspace_size(workspace.path)
        
        return workspace

    async def get_or_create_workspace(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> WorkspaceInfo:
        """Get existing workspace or create new one.
        
        Args:
            user_id: User ID for isolation
            session_id: Session ID for isolation
            metadata: Optional metadata for new workspace
            
        Returns:
            WorkspaceInfo for existing or new workspace
        """
        # Look for existing workspace
        for workspace in self._workspaces.values():
            if workspace.user_id == user_id and workspace.session_id == session_id:
                workspace.last_accessed = datetime.utcnow()
                return workspace
        
        # Create new workspace
        return await self.create_workspace(user_id, session_id, metadata)

    async def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            True if deleted, False if not found
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False
        
        try:
            # Remove directory
            if os.path.exists(workspace.path):
                shutil.rmtree(workspace.path)
            
            # Remove from cache
            del self._workspaces[workspace_id]
            
            logger.info(f"Deleted workspace: {workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete workspace {workspace_id}: {e}")
            return False

    async def list_workspaces(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[WorkspaceInfo]:
        """List workspaces.
        
        Args:
            user_id: Filter by user ID
            session_id: Filter by session ID
            
        Returns:
            List of WorkspaceInfo
        """
        workspaces = list(self._workspaces.values())
        
        if user_id:
            workspaces = [w for w in workspaces if w.user_id == user_id]
        if session_id:
            workspaces = [w for w in workspaces if w.session_id == session_id]
        
        return workspaces

    async def cleanup_expired_workspaces(self) -> int:
        """Cleanup expired workspaces.
        
        Removes workspaces that haven't been accessed within max_age_hours.
        
        Returns:
            Number of workspaces cleaned up
        """
        if not self._config.workspace.auto_cleanup:
            return 0
        
        max_age = timedelta(hours=self._config.workspace.max_age_hours)
        cutoff = datetime.utcnow() - max_age
        
        expired = [
            w for w in self._workspaces.values()
            if w.last_accessed < cutoff
        ]
        
        count = 0
        for workspace in expired:
            if await self.delete_workspace(workspace.workspace_id):
                count += 1
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired workspaces")
        
        return count

    async def start_cleanup_task(self, interval: int = 3600) -> None:
        """Start background cleanup task.
        
        Args:
            interval: Cleanup interval in seconds (default 1 hour)
        """
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    await self.cleanup_expired_workspaces()
                except Exception as e:
                    logger.error(f"Workspace cleanup error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started workspace cleanup task (interval: {interval}s)")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("Stopped workspace cleanup task")

    async def shutdown(self) -> None:
        """Shutdown workspace manager."""
        await self.stop_cleanup_task()
        logger.info("Workspace manager shutdown")


# Global workspace manager instance
_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """Get or create the global workspace manager instance."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
        logger.info("Workspace manager initialized")
    return _workspace_manager


async def cleanup_workspace_manager() -> None:
    """Cleanup the global workspace manager."""
    global _workspace_manager
    if _workspace_manager:
        await _workspace_manager.shutdown()
        _workspace_manager = None
        logger.info("Workspace manager cleaned up")
