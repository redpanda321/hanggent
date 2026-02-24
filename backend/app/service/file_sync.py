"""File sync service for on-demand workspace synchronization to sandboxes.

Provides methods to sync local workspace files to sandbox environments,
supporting both Docker and Daytona sandboxes.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("file_sync")


@dataclass
class SyncResult:
    """Result of a file sync operation."""
    filename: str
    local_path: str
    remote_path: str
    size: int
    success: bool
    error: Optional[str] = None
    synced_at: Optional[str] = None


@dataclass
class SyncSummary:
    """Summary of a batch sync operation."""
    total_files: int
    synced_files: int
    failed_files: int
    total_bytes: int
    synced_bytes: int
    results: List[SyncResult]
    started_at: str
    completed_at: str
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_files == 0:
            return 100.0
        return (self.synced_files / self.total_files) * 100


class FileSyncService:
    """Service for syncing files to sandbox environments.
    
    Supports on-demand file synchronization from local workspace
    to running sandboxes (Docker or Daytona).
    """
    
    # Default file patterns to exclude from sync
    DEFAULT_EXCLUDE_PATTERNS = [
        "__pycache__",
        ".git",
        ".venv",
        "node_modules",
        ".env",
        ".env.local",
        "*.pyc",
        "*.pyo",
        ".DS_Store",
        "Thumbs.db",
    ]
    
    # Maximum file size to sync (default 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    def __init__(
        self,
        sandbox_client,
        exclude_patterns: Optional[List[str]] = None,
        max_file_size: int = MAX_FILE_SIZE,
    ):
        """Initialize file sync service.
        
        Args:
            sandbox_client: Sandbox client (Docker or Daytona)
            exclude_patterns: Patterns to exclude from sync
            max_file_size: Maximum file size to sync in bytes
        """
        self._client = sandbox_client
        self._exclude_patterns = exclude_patterns or self.DEFAULT_EXCLUDE_PATTERNS
        self._max_file_size = max_file_size
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from sync."""
        name = path.name
        path_str = str(path)
        
        for pattern in self._exclude_patterns:
            if pattern.startswith("*"):
                # Extension pattern like *.pyc
                if name.endswith(pattern[1:]):
                    return True
            elif pattern in path_str.split(os.sep):
                # Directory pattern
                return True
            elif name == pattern:
                # Exact match
                return True
        
        return False
    
    def _get_files_to_sync(
        self,
        workspace_path: str,
        file_paths: Optional[List[str]] = None,
    ) -> List[Tuple[Path, str]]:
        """Get list of files to sync.
        
        Args:
            workspace_path: Base workspace directory
            file_paths: Optional specific files to sync (relative paths)
            
        Returns:
            List of (local_path, relative_path) tuples
        """
        workspace = Path(workspace_path).resolve()
        files_to_sync = []
        
        if file_paths:
            # Sync specific files
            for rel_path in file_paths:
                local_path = workspace / rel_path
                if local_path.is_file() and not self._should_exclude(local_path):
                    files_to_sync.append((local_path, rel_path))
        else:
            # Sync all files in workspace
            for local_path in workspace.rglob("*"):
                if local_path.is_file() and not self._should_exclude(local_path):
                    rel_path = str(local_path.relative_to(workspace))
                    files_to_sync.append((local_path, rel_path))
        
        return files_to_sync
    
    async def sync_file(
        self,
        sandbox_id: str,
        local_path: str,
        remote_path: str,
    ) -> SyncResult:
        """Sync a single file to sandbox.
        
        Args:
            sandbox_id: Target sandbox ID
            local_path: Local file path
            remote_path: Remote path inside sandbox
            
        Returns:
            SyncResult with operation outcome
        """
        local_file = Path(local_path)
        
        # Check file exists
        if not local_file.exists():
            return SyncResult(
                filename=local_file.name,
                local_path=str(local_file),
                remote_path=remote_path,
                size=0,
                success=False,
                error="File not found",
            )
        
        # Check file size
        file_size = local_file.stat().st_size
        if file_size > self._max_file_size:
            return SyncResult(
                filename=local_file.name,
                local_path=str(local_file),
                remote_path=remote_path,
                size=file_size,
                success=False,
                error=f"File too large ({file_size} > {self._max_file_size} bytes)",
            )
        
        try:
            # Upload file to sandbox
            success = await self._client.upload_file(
                sandbox_id=sandbox_id,
                local_path=str(local_file),
                remote_path=remote_path,
            )
            
            return SyncResult(
                filename=local_file.name,
                local_path=str(local_file),
                remote_path=remote_path,
                size=file_size,
                success=success,
                synced_at=datetime.utcnow().isoformat() if success else None,
                error=None if success else "Upload failed",
            )
            
        except Exception as e:
            logger.error(f"Failed to sync file {local_path}: {e}")
            return SyncResult(
                filename=local_file.name,
                local_path=str(local_file),
                remote_path=remote_path,
                size=file_size,
                success=False,
                error=str(e),
            )
    
    async def sync_workspace_to_sandbox(
        self,
        sandbox_id: str,
        workspace_path: str,
        remote_base_path: str = "/workspace",
        file_paths: Optional[List[str]] = None,
        concurrency: int = 5,
    ) -> SyncSummary:
        """Sync workspace files to sandbox on demand.
        
        Args:
            sandbox_id: Target sandbox ID
            workspace_path: Local workspace directory
            remote_base_path: Base path inside sandbox
            file_paths: Optional specific files to sync (relative paths)
            concurrency: Number of concurrent uploads
            
        Returns:
            SyncSummary with operation results
        """
        started_at = datetime.utcnow().isoformat()
        files_to_sync = self._get_files_to_sync(workspace_path, file_paths)
        
        if not files_to_sync:
            return SyncSummary(
                total_files=0,
                synced_files=0,
                failed_files=0,
                total_bytes=0,
                synced_bytes=0,
                results=[],
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat(),
            )
        
        logger.info(f"Syncing {len(files_to_sync)} files to sandbox {sandbox_id}")
        
        # Sync files with limited concurrency
        semaphore = asyncio.Semaphore(concurrency)
        
        async def sync_with_limit(local_path: Path, rel_path: str) -> SyncResult:
            async with semaphore:
                remote_path = f"{remote_base_path}/{rel_path}".replace("\\", "/")
                return await self.sync_file(sandbox_id, str(local_path), remote_path)
        
        # Run sync tasks
        tasks = [
            sync_with_limit(local_path, rel_path)
            for local_path, rel_path in files_to_sync
        ]
        results = await asyncio.gather(*tasks)
        
        # Calculate summary
        synced = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        total_bytes = sum(r.size for r in results)
        synced_bytes = sum(r.size for r in synced)
        
        completed_at = datetime.utcnow().isoformat()
        
        logger.info(
            f"Sync complete: {len(synced)}/{len(results)} files, "
            f"{synced_bytes}/{total_bytes} bytes"
        )
        
        return SyncSummary(
            total_files=len(results),
            synced_files=len(synced),
            failed_files=len(failed),
            total_bytes=total_bytes,
            synced_bytes=synced_bytes,
            results=list(results),
            started_at=started_at,
            completed_at=completed_at,
        )
    
    async def sync_file_content(
        self,
        sandbox_id: str,
        content: bytes,
        remote_path: str,
        filename: str = "uploaded_file",
    ) -> SyncResult:
        """Sync file content directly to sandbox.
        
        Args:
            sandbox_id: Target sandbox ID
            content: File content as bytes
            remote_path: Remote path inside sandbox
            filename: Filename for display
            
        Returns:
            SyncResult with operation outcome
        """
        # Check content size
        content_size = len(content)
        if content_size > self._max_file_size:
            return SyncResult(
                filename=filename,
                local_path="<memory>",
                remote_path=remote_path,
                size=content_size,
                success=False,
                error=f"Content too large ({content_size} > {self._max_file_size} bytes)",
            )
        
        try:
            # Write content to sandbox using sandbox client's fs
            # This method varies by client type
            if hasattr(self._client, '_get_client'):
                # Daytona client
                client = self._client._get_client()
                info = self._client._get_cached_sandbox(sandbox_id)
                if info and info.metadata.get("daytona_id"):
                    await asyncio.to_thread(
                        client.sandbox.fs.write,
                        info.metadata["daytona_id"],
                        remote_path,
                        content,
                    )
                    return SyncResult(
                        filename=filename,
                        local_path="<memory>",
                        remote_path=remote_path,
                        size=content_size,
                        success=True,
                        synced_at=datetime.utcnow().isoformat(),
                    )
            
            # Fallback: write to temp file and upload
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                success = await self._client.upload_file(
                    sandbox_id=sandbox_id,
                    local_path=tmp_path,
                    remote_path=remote_path,
                )
                return SyncResult(
                    filename=filename,
                    local_path="<memory>",
                    remote_path=remote_path,
                    size=content_size,
                    success=success,
                    synced_at=datetime.utcnow().isoformat() if success else None,
                )
            finally:
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Failed to sync content to {remote_path}: {e}")
            return SyncResult(
                filename=filename,
                local_path="<memory>",
                remote_path=remote_path,
                size=content_size,
                success=False,
                error=str(e),
            )


# Singleton instance cache
_sync_services = {}


def get_file_sync_service(sandbox_client, **kwargs) -> FileSyncService:
    """Get or create a FileSyncService for a sandbox client.
    
    Args:
        sandbox_client: Sandbox client instance
        **kwargs: Additional arguments for FileSyncService
        
    Returns:
        FileSyncService instance
    """
    client_id = id(sandbox_client)
    if client_id not in _sync_services:
        _sync_services[client_id] = FileSyncService(sandbox_client, **kwargs)
    return _sync_services[client_id]
