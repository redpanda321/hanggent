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

import io
import json
import logging
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session, desc, select

from app.component.auth import Auth, auth_must
from app.component.database import session
from app.model.chat.chat_history import ChatHistory

logger = logging.getLogger("server_logs")

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/export", name="export user logs")
def export_logs(session: Session = Depends(session), auth: Auth = Depends(auth_must)):
    """Export user's chat history and task metadata as a downloadable zip."""
    user_id = auth.user.id

    # Fetch user's recent chat histories (last 200)
    histories = session.exec(
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .order_by(desc(ChatHistory.id))
        .limit(200)
    ).all()

    # Build export data
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "user_id": user_id,
        "total_records": len(histories),
        "histories": [
            {
                "id": h.id,
                "task_id": h.task_id,
                "project_id": h.project_id,
                "project_name": h.project_name,
                "question": h.question,
                "language": h.language,
                "model_platform": h.model_platform,
                "model_type": h.model_type,
                "summary": h.summary,
                "tokens": h.tokens,
                "status": h.status,
                "created_at": h.created_at.isoformat() if h.created_at else None,
                "updated_at": h.updated_at.isoformat() if h.updated_at else None,
            }
            for h in histories
        ],
    }

    # Create zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("chat_history.json", json.dumps(export_data, indent=2, ensure_ascii=False))

    buf.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"hanggent-logs-{timestamp}.zip"

    logger.info("Logs exported", extra={"user_id": user_id, "records": len(histories)})

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
