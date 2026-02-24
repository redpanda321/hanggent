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

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_pagination import add_pagination

logger = logging.getLogger("server_main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server startup/shutdown lifecycle."""
    # Startup: auto-start OpenClaw gateways for all configured users
    asyncio.create_task(_auto_start_openclaw())
    yield


async def _auto_start_openclaw():
    """Fire-and-forget: start all configured OpenClaw gateways after deploy."""
    await asyncio.sleep(5)  # Wait for DB connections to stabilize
    try:
        from app.service import openclaw_service

        result = await openclaw_service.start_all_configured_bots()
        logger.info("OpenClaw auto-start result: %s", result)
    except Exception as e:
        logger.warning("OpenClaw auto-start failed: %s", e)


api = FastAPI(
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan,
)
add_pagination(api)
