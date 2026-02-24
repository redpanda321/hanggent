"""Backend service HTTP client.

Provides a typed async client for the Server (port 3001) to call
the Backend (port 5001) for operations that must happen server-side
(e.g., validating admin API keys without exposing them to the browser).
"""
import httpx
from app.component.environment import env
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("backend_client")

BACKEND_URL = env("BACKEND_URL", "http://localhost:5001")
_TIMEOUT = 30.0  # seconds – validation creates a real agent + live API call


async def validate_model(
    model_platform: str,
    model_type: str,
    api_key: str,
    url: str | None = None,
    extra_params: dict | None = None,
) -> dict:
    """Call Backend POST /model/validate and return the result dict.

    Returns dict with keys: is_valid, is_tool_calls, message
    Raises httpx.HTTPStatusError on 4xx/5xx from the Backend.
    """
    payload: dict = {
        "model_platform": model_platform,
        "model_type": model_type,
        "api_key": api_key,
    }
    if url:
        payload["url"] = url
    if extra_params:
        payload["extra_params"] = extra_params

    logger.info(
        "Proxying model validation to backend",
        extra={"platform": model_platform, "model_type": model_type, "backend_url": BACKEND_URL},
    )

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{BACKEND_URL}/model/validate", json=payload)
        resp.raise_for_status()
        return resp.json()
