# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

"""Chat file upload / list controller.

Endpoints consumed by the frontend:
  GET  /chat/files?task_id=...        → list project files
  POST /chat/files/upload             → upload a file (multipart form)
"""

import logging
import mimetypes
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session, col, select

from app.component.auth import Auth, auth_must
from app.component.database import session
from app.model.chat.chat_file import ChatFile, ChatFileOut

logger = logging.getLogger("server_chat_files")

router = APIRouter(prefix="/chat", tags=["Chat Files"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Maximum upload size: 50 MB
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunks


def _public_dir() -> str:
    """Return the resolved PUBLIC_DIR (same logic as main.py).

    main.py: os.path.join(os.path.dirname(server/main.py), "app", "public")
    i.e. <server_root>/app/public
    """
    if os.environ.get("PUBLIC_DIR"):
        return os.environ["PUBLIC_DIR"]
    # server_root = <repo>/hanggent/server
    # __file__: server/app/controller/chat/files_controller.py
    #   dirname → server/app/controller/chat
    #   ..      → server/app/controller
    #   ../..   → server/app
    #   ../../..→ server
    server_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    return os.path.join(server_root, "app", "public")


def _file_dir(user_id: int, task_id: str) -> str:
    """Return the on-disk directory for a user/task pair, creating it if needed."""
    base = os.path.join(_public_dir(), "files", str(user_id), task_id)
    os.makedirs(base, exist_ok=True)
    return base


def _unique_filename(directory: str, original: str) -> str:
    """Avoid name collisions by prepending a short UUID when the name exists."""
    if not os.path.exists(os.path.join(directory, original)):
        return original
    stem, ext = os.path.splitext(original)
    return f"{stem}_{uuid.uuid4().hex[:8]}{ext}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/files", name="list chat files", response_model=list[ChatFileOut])
def list_files(
    task_id: str = Query(..., description="Project / task ID"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Return every non-deleted file belonging to *task_id* for the current user."""
    user_id = auth.user.id

    stmt = (
        select(ChatFile)
        .where(
            ChatFile.user_id == user_id,
            ChatFile.task_id == task_id,
            col(ChatFile.deleted_at).is_(None),
        )
        .order_by(ChatFile.id)
    )
    rows = session.exec(stmt).all()
    logger.debug("Listed files", extra={"user_id": user_id, "task_id": task_id, "count": len(rows)})
    return [ChatFileOut(filename=r.filename, url=r.url) for r in rows]


@router.post("/files/upload", name="upload chat file", response_model=ChatFileOut)
async def upload_file(
    task_id: str = Form(..., description="Project / task ID"),
    file: UploadFile = File(...),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Stream-upload a file and persist metadata in the DB.

    The file is written to ``PUBLIC_DIR/files/<user_id>/<task_id>/<filename>``
    and served via the existing ``/public`` static-files mount.
    """
    user_id = auth.user.id

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # ---- stream to disk ------------------------------------------------
    directory = _file_dir(user_id, task_id)
    safe_name = _unique_filename(directory, file.filename)
    dest = os.path.join(directory, safe_name)

    total_size = 0
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > _MAX_UPLOAD_BYTES:
                    # Clean up partial file
                    f.close()
                    os.remove(dest)
                    raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("File upload I/O error", extra={"error": str(exc)}, exc_info=True)
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=500, detail="File upload failed")

    # ---- DB record ------------------------------------------------------
    mime = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    public_url = f"/public/files/{user_id}/{task_id}/{safe_name}"

    chat_file = ChatFile(
        user_id=user_id,
        task_id=task_id,
        filename=safe_name,
        file_size=total_size,
        mime_type=mime,
        storage_path=dest,
        url=public_url,
    )
    session.add(chat_file)
    session.commit()
    session.refresh(chat_file)

    logger.info(
        "File uploaded",
        extra={"user_id": user_id, "task_id": task_id, "filename": safe_name, "size": total_size},
    )
    return ChatFileOut(filename=chat_file.filename, url=chat_file.url)


@router.delete("/files", name="delete chat files")
def delete_files(
    task_id: str = Query(..., description="Project / task ID"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Soft-delete all files for a project and remove them from disk."""
    user_id = auth.user.id

    stmt = (
        select(ChatFile)
        .where(
            ChatFile.user_id == user_id,
            ChatFile.task_id == task_id,
            col(ChatFile.deleted_at).is_(None),
        )
    )
    rows = session.exec(stmt).all()
    count = 0
    for row in rows:
        # Soft-delete via AbstractModel (sets deleted_at)
        row.delete(session)
        # Remove file from disk
        if row.storage_path and os.path.exists(row.storage_path):
            try:
                os.remove(row.storage_path)
            except OSError as exc:
                logger.warning("Could not remove file from disk", extra={"path": row.storage_path, "error": str(exc)})
        count += 1

    logger.info("Deleted files", extra={"user_id": user_id, "task_id": task_id, "count": count})
    return {"deleted": count}
