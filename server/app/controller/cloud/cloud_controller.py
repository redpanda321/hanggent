"""Cloud key resolution controller.

Resolves a user's cloud model request to the actual admin-configured
provider API key and endpoint, so the backend can call the real LLM API.
"""
import logging
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select
from sqlalchemy.exc import ProgrammingError, OperationalError, InternalError

from app.component.auth import Auth, auth_must
from app.component.database import session
from app.model.admin.llm_config import AdminLLMConfig, ConfigStatus
from app.model.user.key import Key, KeyStatus

logger = logging.getLogger("server_cloud_controller")

router = APIRouter(tags=["Cloud"])


class CloudKeyResolution(BaseModel):
    """Response from cloud key resolution."""
    api_key: str
    api_url: str
    provider_name: str
    model_type: str


_PROVIDER_ALIASES: dict[str, str] = {
    "gemini": "google",
    "google": "google",
    "hanggent": "hanggent",
    "hangent": "hanggent",
    "hanggent-cloud": "hanggent",
    "hanggent_cloud": "hanggent",
    "new-api": "hanggent",
    "new_api": "hanggent",
    "newapi": "hanggent",
    "glm": "z-ai",
    "chatglm": "z-ai",
    "zhipu": "z-ai",
    "zai": "z-ai",
    "z-ai": "z-ai",
    "bigmodel": "z-ai",
}


def _normalize_provider(provider_name: str) -> str:
    name = (provider_name or "").lower().strip()
    return _PROVIDER_ALIASES.get(name, name)


def _resolve_model_type(*, provider_name: str, model_type: str, endpoint_url: str | None) -> str:
    resolved = (model_type or "").strip()
    provider = (provider_name or "").lower().strip()
    endpoint = (endpoint_url or "").lower().strip()

    # OpenRouter uses OpenAI-compatible endpoints but expects vendor-prefixed model ids
    # for many models (e.g. "openai/gpt-4.1").
    if provider == "openrouter" or "openrouter.ai" in endpoint:
        if "/" not in resolved and (resolved.startswith("gpt") or resolved.startswith("o")):
            return f"openai/{resolved}"

    return resolved


@router.post("/cloud/resolve-key", name="resolve cloud key", response_model=CloudKeyResolution)
async def resolve_cloud_key(
    provider_name: str = Query(..., description="Provider name (e.g. openai, anthropic, gemini)"),
    model_type: str = Query(..., description="Model type (e.g. gpt-4.1, claude-sonnet-4-5)"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Resolve a cloud model request to real provider API credentials.

    Validates the user has an active cloud key, then looks up the
    admin-configured API key for the requested provider.
    Returns the real API key and endpoint URL for the backend to use.
    """
    user_id = auth.user.id

    # 1. Ensure user has an active cloud key (authorization check / bookkeeping)
    user_key = session.exec(
        select(Key)
        .where(Key.user_id == user_id)
        .where(Key.status == KeyStatus.active)
    ).first()

    if not user_key:
        value = f"hg_{secrets.token_urlsafe(32)}"
        user_key = Key(user_id=user_id, value=value, status=KeyStatus.active)
        session.add(user_key)
        session.commit()
        session.refresh(user_key)
        logger.info("User cloud key auto-provisioned during resolve", extra={"user_id": user_id, "key_id": user_key.id})

    # 2. Look up admin-configured provider
    try:
        # Normalize provider name for lookup (frontend may use aliases like "gemini")
        provider_lookup = _normalize_provider(provider_name)

        admin_config = session.exec(
            select(AdminLLMConfig)
            .where(AdminLLMConfig.provider_name == provider_lookup)
            .where(AdminLLMConfig.status == ConfigStatus.enabled)
            .order_by(AdminLLMConfig.priority.desc())
        ).first()

        if not admin_config:
            logger.warning("No admin config found for provider", extra={
                "user_id": user_id,
                "provider_name": provider_lookup,
            })
            raise HTTPException(
                status_code=404,
                detail=f"Cloud provider '{provider_name}' is not configured. "
                       f"Ask the admin to add an API key for this provider.",
            )

        if not admin_config.api_key:
            raise HTTPException(
                status_code=503,
                detail=f"Cloud provider '{provider_name}' has no API key configured.",
            )

        resolved_model_type = _resolve_model_type(
            provider_name=admin_config.provider_name,
            model_type=model_type,
            endpoint_url=admin_config.endpoint_url,
        )

        logger.info("Cloud key resolved", extra={
            "user_id": user_id,
            "provider_name": provider_lookup,
            "has_endpoint": bool(admin_config.endpoint_url),
        })

        return CloudKeyResolution(
            api_key=admin_config.api_key,
            api_url=admin_config.endpoint_url or "",
            provider_name=admin_config.provider_name,
            model_type=resolved_model_type,
        )

    except HTTPException:
        raise
    except (ProgrammingError, OperationalError) as e:
        logger.error("Database schema error in resolve_cloud_key", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")
    except Exception as e:
        logger.error("Failed to resolve cloud key", extra={
            "user_id": user_id,
            "provider_name": provider_name,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve cloud provider credentials.")


class AvailableProviderOut(BaseModel):
    """A configured cloud provider visible to any authenticated user."""
    provider_name: str
    display_name: str
    model_type: str


@router.get(
    "/cloud/available-providers",
    name="get available cloud providers",
    response_model=List[AvailableProviderOut],
)
async def get_available_cloud_providers(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Return the list of admin-configured cloud providers any user can query.

    This lets the frontend know which providers are actually usable so it
    can auto-select a model whose provider is configured, avoiding the
    404 fallback noise.
    """
    try:
        configs = session.exec(
            select(AdminLLMConfig).where(AdminLLMConfig.status == ConfigStatus.enabled)
        ).all()

        results: list[AvailableProviderOut] = []
        for c in configs:
            if not c.api_key:
                continue
            model_type = getattr(c, "model_type", "") or ""
            results.append(AvailableProviderOut(
                provider_name=c.provider_name,
                display_name=c.display_name or c.provider_name,
                model_type=model_type,
            ))
        return results
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.warning(
            "Database schema not ready in get_available_cloud_providers",
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=503,
            detail="Cloud providers are temporarily unavailable due to a database schema issue.",
        )
    except Exception as e:
        logger.error(
            "Failed to list available cloud providers",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Cloud providers are temporarily unavailable.",
        )
