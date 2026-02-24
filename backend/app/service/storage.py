"""Storage manager for file operations with streaming upload support.

Provides file storage operations including streaming uploads for large files,
file validation, and workspace isolation.
"""

import asyncio
import hashlib
import mimetypes
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, BinaryIO, Optional

import aiofiles
import aiofiles.os

from app.config import get_config
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("storage")


@dataclass
class FileInfo:
    """Information about a stored file."""
    file_id: str
    filename: str
    path: str
    size: int
    mime_type: str
    checksum: str
    created_at: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: dict = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "path": self.path,
            "size": self.size,
            "mime_type": self.mime_type,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": self.metadata or {},
        }


class StorageError(Exception):
    """Storage operation error."""
    pass


class FileSizeExceededError(StorageError):
    """File size exceeds limit."""
    pass


class InvalidFileTypeError(StorageError):
    """File type not allowed."""
    pass


class StorageManager:
    """Manages file storage with streaming upload support.
    
    Supports:
    - Streaming uploads for large files (up to 50MB default)
    - Chunk-based upload for resumable transfers
    - File type validation
    - Checksum verification
    - Workspace isolation per user/session
    """

    def __init__(self):
        """Initialize storage manager."""
        self._config = get_config()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure storage directories exist."""
        dirs = [
            self._config.get_workspace_path(),
            self._config.get_temp_path(),
            self._config.get_upload_path(),
        ]
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)

    def _get_workspace_path(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Get workspace path with isolation."""
        return self._config.get_workspace_path(user_id, session_id)

    def _validate_file_extension(self, filename: str) -> bool:
        """Validate file extension is allowed."""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self._config.file.allowed_extensions

    def _generate_file_id(self) -> str:
        """Generate unique file ID."""
        return uuid.uuid4().hex

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type for filename."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"

    async def _compute_checksum(self, file_path: str) -> str:
        """Compute SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    async def upload_stream(
        self,
        filename: str,
        stream: AsyncIterator[bytes],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        content_length: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> FileInfo:
        """Upload file from async stream.
        
        Streams file data directly to disk without loading entire file
        into memory, suitable for large files.
        
        Args:
            filename: Original filename
            stream: Async iterator of file chunks
            user_id: User ID for workspace isolation
            session_id: Session ID for workspace isolation
            content_length: Expected file size (optional)
            metadata: Additional metadata to store
            
        Returns:
            FileInfo with uploaded file details
            
        Raises:
            InvalidFileTypeError: If file type not allowed
            FileSizeExceededError: If file exceeds size limit
        """
        # Validate extension
        if not self._validate_file_extension(filename):
            raise InvalidFileTypeError(
                f"File type not allowed: {os.path.splitext(filename)[1]}"
            )

        # Check content length if provided
        max_size = self._config.file.max_file_size
        if content_length and content_length > max_size:
            raise FileSizeExceededError(
                f"File size {content_length} exceeds limit {max_size}"
            )

        file_id = self._generate_file_id()
        workspace = self._get_workspace_path(user_id, session_id)
        os.makedirs(workspace, exist_ok=True)

        # Use unique filename to prevent collisions
        safe_filename = f"{file_id}_{filename}"
        file_path = os.path.join(workspace, safe_filename)
        temp_path = os.path.join(self._config.get_temp_path(), f"{file_id}.tmp")

        try:
            # Stream to temp file first
            total_size = 0
            async with aiofiles.open(temp_path, "wb") as f:
                async for chunk in stream:
                    total_size += len(chunk)
                    if total_size > max_size:
                        raise FileSizeExceededError(
                            f"File size exceeds limit {max_size}"
                        )
                    await f.write(chunk)

            # Compute checksum
            checksum = await self._compute_checksum(temp_path)

            # Move to final location
            await aiofiles.os.rename(temp_path, file_path)

            file_info = FileInfo(
                file_id=file_id,
                filename=filename,
                path=file_path,
                size=total_size,
                mime_type=self._get_mime_type(filename),
                checksum=checksum,
                created_at=datetime.utcnow(),
                user_id=user_id,
                session_id=session_id,
                metadata=metadata,
            )

            logger.info(
                f"Uploaded file: {filename} ({total_size} bytes)",
                extra={"file_id": file_id, "user_id": user_id},
            )
            return file_info

        except Exception as e:
            # Cleanup on error
            for path in [temp_path, file_path]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
            raise

    async def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> FileInfo:
        """Upload file from file-like object.
        
        Args:
            file: File-like object to upload
            filename: Original filename
            user_id: User ID for workspace isolation
            session_id: Session ID for workspace isolation
            metadata: Additional metadata
            
        Returns:
            FileInfo with uploaded file details
        """
        chunk_size = self._config.file.chunk_size

        async def file_stream():
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        return await self.upload_stream(
            filename=filename,
            stream=file_stream(),
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
        )

    async def download_stream(
        self,
        file_path: str,
    ) -> AsyncIterator[bytes]:
        """Stream file content for download.
        
        Args:
            file_path: Path to file
            
        Yields:
            File content chunks
        """
        chunk_size = self._config.file.chunk_size
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def get_file(
        self,
        file_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[FileInfo]:
        """Get file info by ID.
        
        Args:
            file_id: File ID
            user_id: User ID for workspace validation
            session_id: Session ID for workspace validation
            
        Returns:
            FileInfo or None if not found
        """
        workspace = self._get_workspace_path(user_id, session_id)
        
        # Search for file with matching ID prefix
        try:
            for filename in os.listdir(workspace):
                if filename.startswith(f"{file_id}_"):
                    file_path = os.path.join(workspace, filename)
                    stat = os.stat(file_path)
                    original_name = filename[len(file_id) + 1:]  # Remove ID prefix
                    
                    return FileInfo(
                        file_id=file_id,
                        filename=original_name,
                        path=file_path,
                        size=stat.st_size,
                        mime_type=self._get_mime_type(original_name),
                        checksum="",  # Not computed for existing files
                        created_at=datetime.fromtimestamp(stat.st_ctime),
                        user_id=user_id,
                        session_id=session_id,
                    )
        except FileNotFoundError:
            pass
        
        return None

    async def delete_file(
        self,
        file_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """Delete a file.
        
        Args:
            file_id: File ID
            user_id: User ID for workspace validation
            session_id: Session ID for workspace validation
            
        Returns:
            True if deleted, False if not found
        """
        file_info = await self.get_file(file_id, user_id, session_id)
        if not file_info:
            return False
        
        try:
            os.remove(file_info.path)
            logger.info(f"Deleted file: {file_id}", extra={"user_id": user_id})
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    async def list_files(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        directory: Optional[str] = None,
    ) -> list[FileInfo]:
        """List files in workspace.
        
        Args:
            user_id: User ID for workspace
            session_id: Session ID for workspace
            directory: Subdirectory to list (optional)
            
        Returns:
            List of FileInfo
        """
        workspace = self._get_workspace_path(user_id, session_id)
        if directory:
            workspace = os.path.join(workspace, directory)
        
        files = []
        try:
            for filename in os.listdir(workspace):
                file_path = os.path.join(workspace, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    
                    # Parse file_id from filename
                    parts = filename.split("_", 1)
                    file_id = parts[0] if len(parts) > 1 else filename
                    original_name = parts[1] if len(parts) > 1 else filename
                    
                    files.append(FileInfo(
                        file_id=file_id,
                        filename=original_name,
                        path=file_path,
                        size=stat.st_size,
                        mime_type=self._get_mime_type(original_name),
                        checksum="",
                        created_at=datetime.fromtimestamp(stat.st_ctime),
                        user_id=user_id,
                        session_id=session_id,
                    ))
        except FileNotFoundError:
            pass
        
        return files

    async def create_directory(
        self,
        directory: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Create directory in workspace.
        
        Args:
            directory: Directory name/path
            user_id: User ID for workspace
            session_id: Session ID for workspace
            
        Returns:
            Full path to created directory
        """
        workspace = self._get_workspace_path(user_id, session_id)
        dir_path = os.path.join(workspace, directory)
        os.makedirs(dir_path, exist_ok=True)
        logger.debug(f"Created directory: {dir_path}")
        return dir_path

    async def cleanup_workspace(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Cleanup workspace directory.
        
        Args:
            user_id: User ID for workspace
            session_id: Session ID for workspace
            
        Returns:
            Number of files deleted
        """
        workspace = self._get_workspace_path(user_id, session_id)
        count = 0
        
        try:
            for filename in os.listdir(workspace):
                file_path = os.path.join(workspace, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    count += 1
            
            logger.info(f"Cleaned up workspace: {count} items", extra={"user_id": user_id})
        except Exception as e:
            logger.error(f"Workspace cleanup error: {e}")
        
        return count


# Global storage manager instance
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """Get or create the global storage manager instance."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
        logger.info("Storage manager initialized")
    return _storage_manager
