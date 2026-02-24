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

"""
IM Channel Configuration — loads ``config/im-channels.json`` and
provides runtime access to shared bot credentials and channel settings.

Environment variables override JSON values:

    HANGGENT_TELEGRAM_BOT_TOKEN  → telegram.shared_bot_token
    HANGGENT_DISCORD_BOT_TOKEN   → discord.shared_bot_token
    HANGGENT_SLACK_BOT_TOKEN     → slack.shared_bot_token
    HANGGENT_SLACK_APP_TOKEN     → slack.shared_app_token
    HANGGENT_SLACK_SIGNING_SECRET → slack.signing_secret
    HANGGENT_WHATSAPP_TOKEN      → whatsapp.business_api_token
    HANGGENT_WHATSAPP_PHONE_ID   → whatsapp.phone_number_id
    HANGGENT_WHATSAPP_VERIFY     → whatsapp.verify_token
    HANGGENT_LINE_ACCESS_TOKEN   → line.channel_access_token
    HANGGENT_LINE_CHANNEL_SECRET → line.channel_secret
    HANGGENT_FEISHU_APP_ID       → feishu.app_id
    HANGGENT_FEISHU_APP_SECRET   → feishu.app_secret
    HANGGENT_FEISHU_VERIFY_TOKEN → feishu.verification_token
    HANGGENT_FEISHU_ENCRYPT_KEY  → feishu.encrypt_key
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_config: dict[str, Any] = {}

# Map env var → (channel, key)
_ENV_OVERRIDES: list[tuple[str, str, str]] = [
    ("HANGGENT_TELEGRAM_BOT_TOKEN", "telegram", "shared_bot_token"),
    ("HANGGENT_DISCORD_BOT_TOKEN", "discord", "shared_bot_token"),
    ("HANGGENT_SLACK_BOT_TOKEN", "slack", "shared_bot_token"),
    ("HANGGENT_SLACK_APP_TOKEN", "slack", "shared_app_token"),
    ("HANGGENT_SLACK_SIGNING_SECRET", "slack", "signing_secret"),
    ("HANGGENT_WHATSAPP_TOKEN", "whatsapp", "business_api_token"),
    ("HANGGENT_WHATSAPP_PHONE_ID", "whatsapp", "phone_number_id"),
    ("HANGGENT_WHATSAPP_VERIFY", "whatsapp", "verify_token"),
    ("HANGGENT_LINE_ACCESS_TOKEN", "line", "channel_access_token"),
    ("HANGGENT_LINE_CHANNEL_SECRET", "line", "channel_secret"),
    ("HANGGENT_FEISHU_APP_ID", "feishu", "app_id"),
    ("HANGGENT_FEISHU_APP_SECRET", "feishu", "app_secret"),
    ("HANGGENT_FEISHU_VERIFY_TOKEN", "feishu", "verification_token"),
    ("HANGGENT_FEISHU_ENCRYPT_KEY", "feishu", "encrypt_key"),
]


def _load_config() -> dict[str, Any]:
    """Load im-channels.json with env var overrides."""
    global _config
    if _config:
        return _config

    config_path = Path(__file__).parent.parent.parent.parent / "config" / "im-channels.json"
    if config_path.exists():
        with open(config_path) as f:
            _config = json.load(f)
        logger.info("Loaded IM channels config from %s", config_path)
    else:
        logger.warning("im-channels.json not found at %s — using defaults", config_path)
        _config = {}

    # Apply env var overrides
    for env_var, channel, key in _ENV_OVERRIDES:
        val = os.getenv(env_var)
        if val:
            _config.setdefault(channel, {})[key] = val

    return _config


def get_config() -> dict[str, Any]:
    """Return the full config dict (loaded lazily)."""
    return _load_config()


def get_channel_config(channel_type: str) -> dict[str, Any]:
    """Return config for a specific channel, or empty dict if not configured."""
    return _load_config().get(channel_type, {})


def is_channel_enabled(channel_type: str) -> bool:
    """Check if a channel is enabled in the config."""
    ch = get_channel_config(channel_type)
    return bool(ch.get("enabled", False))


def get_settings() -> dict[str, Any]:
    """Return the global ``settings`` block."""
    return _load_config().get("settings", {})


def is_auto_registration_enabled() -> bool:
    """Check if auto-registration is enabled globally."""
    return bool(get_settings().get("auto_registration", True))


def get_welcome_message() -> str:
    """Return the welcome message for newly auto-registered users."""
    return get_settings().get(
        "welcome_message",
        "👋 Welcome to Hanggent AI! I'm your personal AI assistant. Just send me a message and I'll help you out.",
    )


def reload_config() -> dict[str, Any]:
    """Force a config reload (e.g., after admin changes)."""
    global _config
    _config = {}
    return _load_config()
