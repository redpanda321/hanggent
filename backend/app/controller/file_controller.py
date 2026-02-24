"""File API controller for file uploads, downloads, and management.

Provides REST API endpoints for streaming file uploads (up to 50MB),
downloads, and file management with workspace isolation.
"""

import os
from typing import Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_config
from app.middleware.auth_middleware import get_current_user_id
from app.service.storage import (
    FileInfo,
    FileSizeExceededError,
    InvalidFileTypeError,
    StorageError,
    get_storage_manager,
)
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("file_controller")

router = APIRouter(prefix="/files", tags=["Files"])


# Request/Response Models
class FileResponse(BaseModel):
    """File information response."""
    file_id: str
    filename: str
    size: int
    mime_type: str
    checksum: str
    created_at: str
    url: Optional[str] = None

    @classmethod
    def from_info(cls, info: FileInfo, base_url: str = "") -> "FileResponse":
        """Create response from FileInfo."""
        return cls(
            file_id=info.file_id,
            filename=info.filename,
            size=info.size,
            mime_type=info.mime_type,
            checksum=info.checksum,
            created_at=info.created_at.isoformat(),
            url=f"{base_url}/files/{info.file_id}" if base_url else None,
        )


class FileListResponse(BaseModel):
    """List of files response."""
    files: list[FileResponse]
    total: int
    directory: Optional[str] = None


class UploadConfigResponse(BaseModel):
    """Upload configuration response."""
    max_file_size: int
    max_file_size_mb: float
    chunk_size: int
    allowed_extensions: list[str]


class CreateDirectoryRequest(BaseModel):
    """Request to create a directory."""
    directory: str = Field(..., description="Directory path to create")


class DirectoryResponse(BaseModel):
    """Directory creation response."""
    path: str
    created: bool


# Endpoints
@router.get("/config", response_model=UploadConfigResponse)
async def get_upload_config():
    """Get file upload configuration.
    
    Returns the maximum file size, chunk size, and allowed file extensions.
    """
    config = get_config()
    return UploadConfigResponse(
        max_file_size=config.file.max_file_size,
        max_file_size_mb=config.file.max_file_size / (1024 * 1024),
        chunk_size=config.file.chunk_size,
        allowed_extensions=config.file.allowed_extensions,
    )


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    metadata: Optional[str] = Form(default=None),
):
    """Upload a file using streaming.
    
    Supports files up to the configured maximum size (default 50MB).
    Files are streamed directly to disk without loading entirely into memory.
    
    Parameters:
    - file: The file to upload (multipart form data)
    - session_id: Optional session ID for workspace isolation
    - metadata: Optional JSON metadata string
    """
    storage = get_storage_manager()
    
    # Get user ID from auth middleware (if available)
    user_id = get_current_user_id(request)
    user_id_str = str(user_id) if user_id else None
    
    # Parse metadata if provided
    meta_dict = None
    if metadata:
        try:
            import json
            meta_dict = json.loads(metadata)
        except Exception:
            pass
    
    try:
        # Get content length if available
        content_length = None
        if file.size:
            content_length = file.size
        elif "content-length" in request.headers:
            try:
                content_length = int(request.headers["content-length"])
            except ValueError:
                pass

        # Stream upload
        async def file_stream():
            chunk_size = get_config().file.chunk_size
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        file_info = await storage.upload_stream(
            filename=file.filename,
            stream=file_stream(),
            user_id=user_id_str,
            session_id=session_id,
            content_length=content_length,
            metadata=meta_dict,
        )

        # Get base URL for file URL
        base_url = str(request.base_url).rstrip("/")
        
        return FileResponse.from_info(file_info, base_url)

    except InvalidFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except FileSizeExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except StorageError as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed",
        )


@router.get("/{file_id}", response_class=StreamingResponse)
async def download_file(
    request: Request,
    file_id: str,
    session_id: Optional[str] = Query(default=None),
):
    """Download a file by ID.
    
    Streams the file content for efficient large file downloads.
    """
    storage = get_storage_manager()
    user_id = get_current_user_id(request)
    user_id_str = str(user_id) if user_id else None
    
    file_info = await storage.get_file(
        file_id=file_id,
        user_id=user_id_str,
        session_id=session_id,
    )
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_id}",
        )
    
    return StreamingResponse(
        storage.download_stream(file_info.path),
        media_type=file_info.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_info.filename}"',
            "Content-Length": str(file_info.size),
        },
    )


@router.get("/{file_id}/info", response_model=FileResponse)
async def get_file_info(
    request: Request,
    file_id: str,
    session_id: Optional[str] = Query(default=None),
):
    """Get file information by ID."""
    storage = get_storage_manager()
    user_id = get_current_user_id(request)
    user_id_str = str(user_id) if user_id else None
    
    file_info = await storage.get_file(
        file_id=file_id,
        user_id=user_id_str,
        session_id=session_id,
    )
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_id}",
        )
    
    base_url = str(request.base_url).rstrip("/")
    return FileResponse.from_info(file_info, base_url)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    request: Request,
    file_id: str,
    session_id: Optional[str] = Query(default=None),
):
    """Delete a file by ID."""
    storage = get_storage_manager()
    user_id = get_current_user_id(request)
    user_id_str = str(user_id) if user_id else None
    
    success = await storage.delete_file(
        file_id=file_id,
        user_id=user_id_str,
        session_id=session_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_id}",
        )


@router.get("/", response_model=FileListResponse)
async def list_files(
    request: Request,
    session_id: Optional[str] = Query(default=None),
    directory: Optional[str] = Query(default=None),
):
    """List files in workspace.
    
    Optionally filter by directory path.
    """
    storage = get_storage_manager()
    user_id = get_current_user_id(request)
    user_id_str = str(user_id) if user_id else None
    
    files = await storage.list_files(
        user_id=user_id_str,
        session_id=session_id,
        directory=directory,
    )
    
    base_url = str(request.base_url).rstrip("/")
    return FileListResponse(
        files=[FileResponse.from_info(f, base_url) for f in files],
        total=len(files),
        directory=directory,
    )


@router.post("/directory", response_model=DirectoryResponse)
async def create_directory(
    request: Request,
    data: CreateDirectoryRequest,
    session_id: Optional[str] = Query(default=None),
):
    """Create a directory in workspace."""
    storage = get_storage_manager()
    user_id = get_current_user_id(request)
    user_id_str = str(user_id) if user_id else None
    
    try:
        path = await storage.create_directory(
            directory=data.directory,
            user_id=user_id_str,
            session_id=session_id,
        )
        return DirectoryResponse(path=path, created=True)
    except Exception as e:
        logger.error(f"Failed to create directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create directory: {str(e)}",
        )


@router.delete("/workspace", status_code=status.HTTP_200_OK)
async def cleanup_workspace(
    request: Request,
    session_id: Optional[str] = Query(default=None),
):
    """Cleanup workspace (delete all files).
    
    WARNING: This will delete all files in the workspace.
    """
    storage = get_storage_manager()
    user_id = get_current_user_id(request)
    user_id_str = str(user_id) if user_id else None
    
    count = await storage.cleanup_workspace(
        user_id=user_id_str,
        session_id=session_id,
    )
    
    return {"deleted": count, "message": f"Cleaned up {count} items"}
