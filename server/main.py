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

import os
import pathlib
import sys

# Add project root to Python path to import shared utils
_project_root = pathlib.Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import logging

from fastapi.staticfiles import StaticFiles

# Import exception handlers to register them
import app.exception.handler  # noqa: F401

# Import middleware to register BabelMiddleware
import app.middleware  # noqa: F401
from app import api
from app.component.environment import auto_include_routers, env

logger = logging.getLogger("server_main")

# Run database migrations on startup (idempotent)
try:
    from app.component.auto_migrate import run_migrations
    if not run_migrations():
        logger.warning("Auto-migration returned False – check logs for details")
except Exception as e:
    logger.error(f"Auto-migration failed during startup: {e}", exc_info=True)

# Auto-seed default admin LLM provider configurations (idempotent)
try:
    # Manual seeding only by default; explicit env opt-in is required to auto-seed.
    auto_seed_default_providers = str(env("AUTO_SEED_DEFAULT_PROVIDERS", "false")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if auto_seed_default_providers:
        from app.component.auto_seed import seed_default_providers
        seed_default_providers()
    else:
        logger.info("Auto-seed default providers disabled by AUTO_SEED_DEFAULT_PROVIDERS")
except Exception as e:
    logger.warning(f"Auto-seed default providers failed during startup: {e}")

# Pre-register all SQLModel tables so FK references resolve at runtime
from app.component.environment import auto_import as _auto_import
for _pkg in ("app.model.mcp", "app.model.user", "app.model.config",
             "app.model.chat", "app.model.provider", "app.model.plan",
             "app.model.pay", "app.model.admin"):
    try:
        _auto_import(_pkg)
    except Exception as _e:
        logger.warning(f"Failed to auto-import {_pkg}: {_e}")

prefix = env("url_prefix", "")
auto_include_routers(api, prefix, "app/controller")
public_dir = os.environ.get("PUBLIC_DIR") or os.path.join(os.path.dirname(__file__), "app", "public")
if not os.path.isdir(public_dir):
    try:
        os.makedirs(public_dir, exist_ok=True)
        logger.warning(f"Public directory did not exist. Created: {public_dir}")
    except Exception as e:
        logger.error(f"Public directory missing and could not be created: {public_dir}. Error: {e}")
        public_dir = None

if public_dir and os.path.isdir(public_dir):
    api.mount("/public", StaticFiles(directory=public_dir), name="public")
else:
    logger.warning("Skipping /public mount because public directory is unavailable")
