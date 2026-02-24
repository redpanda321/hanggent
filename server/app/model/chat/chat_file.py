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

"""ChatFile model – stores metadata for files uploaded to a chat project."""

from pydantic import BaseModel
from sqlmodel import Field, String, Column

from app.model.abstract.model import AbstractModel, DefaultTimes


class ChatFile(AbstractModel, DefaultTimes, table=True):
    """Persisted file metadata linked to a chat project (task)."""

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    task_id: str = Field(sa_column=Column(String(255), index=True))
    filename: str = Field(sa_column=Column(String(512)))
    file_size: int = Field(default=0)
    mime_type: str = Field(default="application/octet-stream", sa_column=Column(String(255)))
    storage_path: str = Field(sa_column=Column(String(1024)))
    url: str = Field(sa_column=Column(String(1024)))


class ChatFileOut(BaseModel):
    """Response schema – matches the frontend's expected contract."""

    filename: str
    url: str
