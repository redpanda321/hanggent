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

import logging
import secrets

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.component.auth import Auth, auth_must
from app.component.database import session
from app.model.user.key import Key, KeyOut, KeyStatus

logger = logging.getLogger("server_user_key_controller")

router = APIRouter(tags=["User"])


@router.get("/user/key", name="get user key", response_model=KeyOut)
def get_user_key(auth: Auth = Depends(auth_must), session: Session = Depends(session)):
    """Get or provision the current user's cloud API key.

    The frontend expects this endpoint to exist at `/api/user/key` (via `url_prefix`).
    If the user does not yet have an active key, one will be created.
    """

    user_id = auth.user.id

    model = session.exec(
        select(Key)
        .where(Key.user_id == user_id)
        .where(Key.status == KeyStatus.active)
        .order_by(Key.id.desc())
    ).first()

    if model is None:
        value = f"hg_{secrets.token_urlsafe(32)}"
        model = Key(user_id=user_id, value=value, status=KeyStatus.active)
        session.add(model)
        session.commit()
        session.refresh(model)
        logger.info("User key provisioned", extra={"user_id": user_id, "key_id": model.id})

    return KeyOut(value=model.value)
