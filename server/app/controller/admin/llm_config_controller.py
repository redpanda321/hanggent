"""Admin LLM Configuration Controller.

Provides endpoints for managing system-wide LLM provider configurations
and model pricing. Only accessible by admin users.
"""
from typing import List, Optional
from decimal import Decimal
from fastapi import Depends, HTTPException, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from sqlalchemy.exc import ProgrammingError, OperationalError, InternalError, SQLAlchemyError
from fastapi_babel import _
from app.component.database import session
from app.component.auth import Auth, auth_must
from app.component.environment import env
from app.model.admin.llm_config import (
    AdminLLMConfig,
    AdminLLMConfigCreate,
    AdminLLMConfigUpdate,
    AdminLLMConfigOut,
    AdminModelPricing,
    AdminModelPricingCreate,
    AdminModelPricingUpdate,
    AdminModelPricingOut,
    ConfigStatus,
    DEFAULT_PROVIDERS,
    DEFAULT_MODEL_PRICING,
)
from app.model.admin.admin_settings import AdminSettings, AdminSettingOut
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("admin_llm_config_controller")

router = APIRouter(prefix="/admin", tags=["Admin LLM Configuration"])

# Admin emails (configured via ADMIN_EMAILS environment variable)
_DEFAULT_ADMIN_EMAILS = ""
_env_admin_emails = env("ADMIN_EMAILS") or ""
_admin_email_candidates = ",".join([_DEFAULT_ADMIN_EMAILS, _env_admin_emails])
ADMIN_EMAILS = [e.strip().lower() for e in _admin_email_candidates.split(",") if e.strip()]


def check_admin(auth: Auth) -> bool:
    """Check if the current user is an admin."""
    try:
        user = auth.user
        user_email = getattr(user, 'email', None)
        user_plan = getattr(user, 'subscription_plan', None)
        logger.info("Admin check", extra={
            "user_id": getattr(user, 'id', None),
            "user_email": user_email,
            "user_plan": user_plan,
            "admin_emails": ADMIN_EMAILS,
        })
        if user_email and user_email.lower().strip() in ADMIN_EMAILS:
            return True
        # Also check for pro subscription as admin access
        if user_plan == "pro":
            return True
        return False
    except Exception as e:
        logger.error("Admin check failed with exception", extra={"error": str(e)}, exc_info=True)
        return False


def require_admin(auth: Auth = Depends(auth_must)) -> Auth:
    """Dependency that requires admin access."""
    if not check_admin(auth):
        user_email = getattr(auth, '_user', None) and getattr(auth._user, 'email', 'unknown')
        logger.warning("Admin access denied", extra={"user_email": user_email, "admin_emails": ADMIN_EMAILS})
        raise HTTPException(status_code=403, detail=_("Admin access required"))
    return auth


def mask_api_key(api_key: str) -> str:
    """Mask API key showing only last 4 characters."""
    if len(api_key) <= 4:
        return "****"
    return "*" * (len(api_key) - 4) + api_key[-4:]


def config_to_out(config: AdminLLMConfig) -> AdminLLMConfigOut:
    """Convert AdminLLMConfig to output model with masked API key."""
    return AdminLLMConfigOut(
        id=config.id,
        provider_name=config.provider_name,
        display_name=config.display_name,
        api_key_masked=mask_api_key(config.api_key),
        endpoint_url=config.endpoint_url,
        model_type=getattr(config, "model_type", "") or "",
        extra_config=config.extra_config,
        status=config.status,
        priority=config.priority,
        rate_limit_rpm=config.rate_limit_rpm,
        rate_limit_tpm=config.rate_limit_tpm,
        notes=config.notes,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


# =====================
# LLM Config Endpoints
# =====================

@router.get("/llm-configs", name="list admin LLM configs", response_model=List[AdminLLMConfigOut])
@traceroot.trace()
async def list_llm_configs(
    status: Optional[ConfigStatus] = None,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """List all admin LLM provider configurations."""
    try:
        query = select(AdminLLMConfig)
        if status is not None:
            query = query.where(AdminLLMConfig.status == status)
        query = query.order_by(AdminLLMConfig.priority.desc(), AdminLLMConfig.provider_name)
        
        configs = session.exec(query).all()
        logger.debug("Admin LLM configs listed", extra={"count": len(configs)})
        return [config_to_out(c) for c in configs]
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.warning(
            "Database schema not ready in list_llm_configs, returning empty list",
            extra={"error": str(e)},
        )
        return []
    except Exception as e:
        logger.error(
            "Failed to list admin LLM configs, returning empty list",
            extra={"error": str(e)},
            exc_info=True,
        )
        return []


@router.get("/llm-configs/{config_id}", name="get admin LLM config", response_model=AdminLLMConfigOut)
@traceroot.trace()
async def get_llm_config(
    config_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Get a specific admin LLM config by ID."""
    try:
        config = session.get(AdminLLMConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=_("Configuration not found"))
        return config_to_out(config)
    except HTTPException:
        raise
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.error("Database schema error in get_llm_config - migration may be pending", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")


@router.post("/llm-configs", name="create admin LLM config", response_model=AdminLLMConfigOut)
@traceroot.trace()
async def create_llm_config(
    config_in: AdminLLMConfigCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Create or update an admin LLM provider configuration (upsert)."""
    if not (config_in.provider_name or "").strip():
        raise HTTPException(status_code=400, detail="provider_name is required")
    if config_in.api_key is None:
        raise HTTPException(status_code=400, detail="api_key is required")

    def _normalize_google_endpoint(url: str | None) -> str | None:
        if not url:
            return url
        stripped = str(url).strip().rstrip("/")
        if stripped == "https://generativelanguage.googleapis.com":
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return url

    try:
        allowed_fields = set(getattr(AdminLLMConfig, "model_fields", {}).keys())

        # Check if provider already exists — upsert if so
        existing = session.exec(
            select(AdminLLMConfig).where(AdminLLMConfig.provider_name == config_in.provider_name)
        ).first()
        if existing:
            update_data = config_in.model_dump(exclude={"provider_name"})

            if (existing.provider_name or "").lower() == "google" and "endpoint_url" in update_data:
                update_data["endpoint_url"] = _normalize_google_endpoint(update_data.get("endpoint_url"))

            for key, value in update_data.items():
                if allowed_fields and key not in allowed_fields:
                    continue
                setattr(existing, key, value)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            logger.info("Admin LLM config upserted (updated existing)", extra={"config_id": existing.id, "provider": existing.provider_name})
            return config_to_out(existing)
        
        create_data = config_in.model_dump()

        if (create_data.get("provider_name") or "").lower() == "google":
            create_data["endpoint_url"] = _normalize_google_endpoint(create_data.get("endpoint_url"))

        if allowed_fields:
            create_data = {key: value for key, value in create_data.items() if key in allowed_fields}

        config = AdminLLMConfig(**create_data)
        session.add(config)
        session.commit()
        session.refresh(config)
        
        logger.info("Admin LLM config created", extra={"config_id": config.id, "provider": config.provider_name})
        return config_to_out(config)
    except HTTPException:
        raise
    except (ProgrammingError, OperationalError, InternalError) as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Database schema error in create_llm_config - migration may be pending", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")
    except SQLAlchemyError as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Database error in create_llm_config", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Database error while saving configuration")
    except Exception as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Unexpected error in create_llm_config", extra={"error": str(e)}, exc_info=True)
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"Failed to save configuration ({error_type}: {str(e)[:240]})")


@router.put("/llm-configs/{config_id}", name="update admin LLM config", response_model=AdminLLMConfigOut)
@traceroot.trace()
async def update_llm_config(
    config_id: int,
    config_update: AdminLLMConfigUpdate,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Update an admin LLM provider configuration."""

    def _normalize_google_endpoint(url: str | None) -> str | None:
        if not url:
            return url
        stripped = str(url).strip().rstrip("/")
        if stripped == "https://generativelanguage.googleapis.com":
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return url

    try:
        allowed_fields = set(getattr(AdminLLMConfig, "model_fields", {}).keys())

        config = session.get(AdminLLMConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=_("Configuration not found"))
        
        update_data = config_update.model_dump(exclude_unset=True)

        if (config.provider_name or "").lower() == "google" and "endpoint_url" in update_data:
            update_data["endpoint_url"] = _normalize_google_endpoint(update_data.get("endpoint_url"))

        for key, value in update_data.items():
            if allowed_fields and key not in allowed_fields:
                continue
            setattr(config, key, value)
        
        session.add(config)
        session.commit()
        session.refresh(config)
        
        logger.info("Admin LLM config updated", extra={"config_id": config.id, "provider": config.provider_name})
        return config_to_out(config)
    except HTTPException:
        raise
    except (ProgrammingError, OperationalError, InternalError) as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Database schema error in update_llm_config - migration may be pending", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")
    except SQLAlchemyError as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Database error in update_llm_config", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Database error while updating configuration")
    except Exception as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Unexpected error in update_llm_config", extra={"error": str(e)}, exc_info=True)
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"Failed to update configuration ({error_type}: {str(e)[:240]})")


@router.delete("/llm-configs/{config_id}", name="delete admin LLM config")
@traceroot.trace()
async def delete_llm_config(
    config_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Delete an admin LLM provider configuration."""
    try:
        config = session.get(AdminLLMConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=_("Configuration not found"))
        
        provider_name = config.provider_name
        session.delete(config)
        session.commit()
        
        logger.info("Admin LLM config deleted", extra={"config_id": config_id, "provider": provider_name})
        return {"message": "Configuration deleted successfully"}
    except HTTPException:
        raise
    except (ProgrammingError, OperationalError, InternalError) as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Database schema error in delete_llm_config - migration may be pending", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")
    except SQLAlchemyError as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Database error in delete_llm_config", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Database error while deleting configuration")
    except Exception as e:
        try:
            session.rollback()
        except Exception:
            pass
        logger.error("Unexpected error in delete_llm_config", extra={"error": str(e)}, exc_info=True)
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"Failed to delete configuration ({error_type}: {str(e)[:240]})")


@router.post("/llm-configs/seed-defaults", name="seed default LLM configs")
@traceroot.trace()
async def seed_default_configs(
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Seed default provider configurations (without API keys)."""
    try:
        created = 0
        skipped = 0
        
        for provider in DEFAULT_PROVIDERS:
            existing = session.exec(
                select(AdminLLMConfig).where(AdminLLMConfig.provider_name == provider["provider_name"])
            ).first()
            if existing:
                skipped += 1
                continue
            
            config = AdminLLMConfig(
                provider_name=provider["provider_name"],
                display_name=provider["display_name"],
                endpoint_url=provider["endpoint_url"],
                model_type=provider.get("model_type", ""),
                api_key="",  # Placeholder, must be configured
                status=ConfigStatus.disabled,  # Disabled until API key is added
            )
            session.add(config)
            created += 1
        
        session.commit()
        logger.info("Default LLM configs seeded", extra={"created": created, "skipped": skipped})
        return {"message": f"Created {created} configs, skipped {skipped} existing"}
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.error("Database schema error in seed_default_configs - migration may be pending", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")


# Pydantic model for the validate request body
class ValidateConfigRequest(BaseModel):
    """Optional overrides for validating an existing admin LLM config."""
    model_type: str | None = None
    api_key: str | None = None


@router.post("/llm-configs/{config_id}/validate", name="validate admin LLM config")
@traceroot.trace()
async def validate_llm_config(
    config_id: int,
    body: ValidateConfigRequest | None = None,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Validate an admin LLM config by making a live API call to the Backend.

    Uses the stored API key unless an override is provided in the request body.
    This keeps admin secrets server-side and never exposes them to the browser.
    """
    from app.component.backend_client import validate_model as backend_validate
    import httpx

    config = session.get(AdminLLMConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail=_("Configuration not found"))

    api_key = (body.api_key if body and body.api_key else None) or config.api_key
    model_type = (body.model_type if body and body.model_type else None) or config.model_type

    if not api_key:
        raise HTTPException(status_code=400, detail=_("API key is required for validation"))
    if not model_type:
        raise HTTPException(status_code=400, detail=_("Model type is required for validation"))

    try:
        # OpenAI-compatible gateways (e.g. hanggent/new-api, together)
        # must validate as "openai-compatible-model" so CAMEL creates the
        # correct OpenAICompatibleModel class (not OpenAIModel).
        _OPENAI_COMPAT = {
            "hanggent",
            "new-api",
            "new_api",
            "together",
            "minimax",
            "kimi",
            "z-ai",
            "xai",
        }
        provider_name = (config.provider_name or "").lower().strip()
        if provider_name in _OPENAI_COMPAT:
            validation_platform = "openai-compatible-model"
        elif provider_name == "openrouter":
            # CAMEL has native ModelPlatformType.OPENROUTER support;
            # validate using the real platform path.
            validation_platform = "openrouter"
        else:
            validation_platform = config.provider_name
        result = await backend_validate(
            model_platform=validation_platform,
            model_type=model_type,
            api_key=api_key,
            url=config.endpoint_url or None,
        )
        return result
    except httpx.HTTPStatusError as e:
        # Forward the Backend's error detail to the frontend
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        logger.warning(
            "Backend validation returned error",
            extra={"config_id": config_id, "status": e.response.status_code, "detail": detail},
        )
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except Exception as e:
        logger.error(
            "Backend validation failed",
            extra={"config_id": config_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=502, detail=_("Failed to reach validation service"))


# ======================
# Model Pricing Endpoints
# ======================

@router.get("/model-pricing", name="list model pricing", response_model=List[AdminModelPricingOut])
@traceroot.trace()
async def list_model_pricing(
    provider_name: Optional[str] = None,
    is_available: Optional[bool] = None,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """List all model pricing configurations."""
    query = select(AdminModelPricing)
    if provider_name:
        query = query.where(AdminModelPricing.provider_name == provider_name)
    if is_available is not None:
        query = query.where(AdminModelPricing.is_available == is_available)
    query = query.order_by(AdminModelPricing.provider_name, AdminModelPricing.model_name)
    
    pricing_list = session.exec(query).all()
    logger.debug("Model pricing listed", extra={"count": len(pricing_list)})
    return pricing_list


@router.get("/model-pricing/{pricing_id}", name="get model pricing", response_model=AdminModelPricingOut)
@traceroot.trace()
async def get_model_pricing(
    pricing_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Get specific model pricing by ID."""
    pricing = session.get(AdminModelPricing, pricing_id)
    if not pricing:
        raise HTTPException(status_code=404, detail=_("Pricing not found"))
    return pricing


@router.post("/model-pricing", name="create model pricing", response_model=AdminModelPricingOut)
@traceroot.trace()
async def create_model_pricing(
    pricing_in: AdminModelPricingCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Create a new model pricing entry."""
    # Check if model pricing already exists
    existing = session.exec(
        select(AdminModelPricing).where(
            AdminModelPricing.provider_name == pricing_in.provider_name,
            AdminModelPricing.model_name == pricing_in.model_name,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=_("Model pricing already exists"))
    
    pricing = AdminModelPricing(**pricing_in.model_dump())
    session.add(pricing)
    session.commit()
    session.refresh(pricing)
    
    logger.info("Model pricing created", extra={"pricing_id": pricing.id, "model": pricing.model_name})
    return pricing


@router.put("/model-pricing/{pricing_id}", name="update model pricing", response_model=AdminModelPricingOut)
@traceroot.trace()
async def update_model_pricing(
    pricing_id: int,
    pricing_update: AdminModelPricingUpdate,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Update a model pricing entry."""
    pricing = session.get(AdminModelPricing, pricing_id)
    if not pricing:
        raise HTTPException(status_code=404, detail=_("Pricing not found"))
    
    update_data = pricing_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pricing, key, value)
    
    session.add(pricing)
    session.commit()
    session.refresh(pricing)
    
    logger.info("Model pricing updated", extra={"pricing_id": pricing.id, "model": pricing.model_name})
    return pricing


@router.delete("/model-pricing/{pricing_id}", name="delete model pricing")
@traceroot.trace()
async def delete_model_pricing(
    pricing_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Delete a model pricing entry."""
    pricing = session.get(AdminModelPricing, pricing_id)
    if not pricing:
        raise HTTPException(status_code=404, detail=_("Pricing not found"))
    
    model_name = pricing.model_name
    session.delete(pricing)
    session.commit()
    
    logger.info("Model pricing deleted", extra={"pricing_id": pricing_id, "model": model_name})
    return {"message": "Pricing deleted successfully"}


@router.post("/model-pricing/seed-defaults", name="seed default model pricing")
@traceroot.trace()
async def seed_default_pricing(
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Seed default model pricing from configuration."""
    created = 0
    skipped = 0
    
    for pricing_data in DEFAULT_MODEL_PRICING:
        existing = session.exec(
            select(AdminModelPricing).where(
                AdminModelPricing.provider_name == pricing_data["provider_name"],
                AdminModelPricing.model_name == pricing_data["model_name"],
            )
        ).first()
        if existing:
            skipped += 1
            continue
        
        pricing = AdminModelPricing(
            provider_name=pricing_data["provider_name"],
            model_name=pricing_data["model_name"],
            display_name=pricing_data.get("display_name", ""),
            input_price_per_million=Decimal(pricing_data["input_price_per_million"]),
            output_price_per_million=Decimal(pricing_data["output_price_per_million"]),
            cost_tier=pricing_data.get("cost_tier", "standard"),
            context_length=pricing_data.get("context_length"),
            is_available=True,
        )
        session.add(pricing)
        created += 1
    
    session.commit()
    logger.info("Default model pricing seeded", extra={"created": created, "skipped": skipped})
    return {"message": f"Created {created} pricing entries, skipped {skipped} existing"}


# ======================
# Export Seed Data Endpoint
# ======================

@router.get("/export-seed-data", name="export seed data")
@traceroot.trace()
async def export_seed_data(
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Export all admin tables as JSON seed data (API keys stripped).

    Returns providers, pricing, and settings suitable for saving as
    fixture files in ``server/fixtures/``.
    """
    try:
        # --- Providers (strip API keys) ---
        configs = session.exec(
            select(AdminLLMConfig).order_by(AdminLLMConfig.provider_name)
        ).all()
        providers = [
            {
                "provider_name": c.provider_name,
                "display_name": c.display_name,
                "endpoint_url": c.endpoint_url,
                "model_type": getattr(c, "model_type", "") or "",
                "extra_config": c.extra_config,
                "status": int(c.status),
                "priority": c.priority,
                "rate_limit_rpm": c.rate_limit_rpm,
                "rate_limit_tpm": c.rate_limit_tpm,
                "notes": c.notes or "",
            }
            for c in configs
        ]

        # --- Pricing ---
        pricing_rows = session.exec(
            select(AdminModelPricing).order_by(
                AdminModelPricing.provider_name,
                AdminModelPricing.model_name,
            )
        ).all()
        pricing = [
            {
                "provider_name": p.provider_name,
                "model_name": p.model_name,
                "display_name": p.display_name,
                "input_price_per_million": str(p.input_price_per_million),
                "output_price_per_million": str(p.output_price_per_million),
                "cost_tier": p.cost_tier,
                "context_length": p.context_length,
                "is_available": p.is_available,
                "notes": p.notes or "",
            }
            for p in pricing_rows
        ]

        # --- Settings ---
        settings_rows = session.exec(
            select(AdminSettings).order_by(AdminSettings.key)
        ).all()
        settings = [
            {
                "key": s.key,
                "value": s.value,
                "description": s.description or "",
            }
            for s in settings_rows
        ]

        return {
            "providers": providers,
            "pricing": pricing,
            "settings": settings,
            "counts": {
                "providers": len(providers),
                "pricing": len(pricing),
                "settings": len(settings),
            },
        }
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.error("Database schema error in export_seed_data", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")


# ======================
# Public Endpoints (for users without their own keys)
# ======================

@router.get("/available-providers", name="get available providers")
@traceroot.trace()
async def get_available_providers(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Get list of available providers (for users to see which providers have admin keys configured)."""
    try:
        configs = session.exec(
            select(AdminLLMConfig).where(AdminLLMConfig.status == ConfigStatus.enabled)
        ).all()
        
        return [
            {
                "provider_name": c.provider_name,
                "display_name": c.display_name,
                "has_rate_limit": c.rate_limit_rpm is not None or c.rate_limit_tpm is not None,
            }
            for c in configs
        ]
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.error("Database schema error in get_available_providers - migration may be pending", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")


@router.get("/public-model-pricing", name="get public model pricing")
@traceroot.trace()
async def get_public_model_pricing(
    provider_name: Optional[str] = None,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Get model pricing (public view for all authenticated users).

    Prices are adjusted by the global additional fee percentage so that
    users see the effective cost they will be billed.
    """
    query = select(AdminModelPricing).where(AdminModelPricing.is_available == True)
    if provider_name:
        query = query.where(AdminModelPricing.provider_name == provider_name)
    query = query.order_by(AdminModelPricing.provider_name, AdminModelPricing.model_name)

    pricing_list = session.exec(query).all()

    # Apply additional fee multiplier
    fee_percent = AdminSettings.get_additional_fee_percent(session)
    multiplier = 1 + fee_percent / 100

    return [
        {
            "provider_name": p.provider_name,
            "model_name": p.model_name,
            "display_name": p.display_name,
            "input_price_per_million": round(float(p.input_price_per_million) * multiplier, 4),
            "output_price_per_million": round(float(p.output_price_per_million) * multiplier, 4),
            "base_input_price_per_million": float(p.input_price_per_million),
            "base_output_price_per_million": float(p.output_price_per_million),
            "additional_fee_percent": fee_percent,
            "cost_tier": p.cost_tier,
            "context_length": p.context_length,
        }
        for p in pricing_list
    ]


# ======================
# Admin Settings Endpoints
# ======================

@router.get("/settings", name="list admin settings")
@traceroot.trace()
async def list_admin_settings(
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """List all admin settings."""
    try:
        rows = session.exec(select(AdminSettings)).all()
        return [AdminSettingOut.model_validate(r, from_attributes=True) for r in rows]
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.warning("Database schema not ready in list_admin_settings", extra={"error": str(e)})
        return []


@router.get("/settings/{key}", name="get admin setting")
@traceroot.trace()
async def get_admin_setting(
    key: str,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Get a single admin setting by key."""
    try:
        row = session.exec(select(AdminSettings).where(AdminSettings.key == key)).first()
        if not row:
            raise HTTPException(status_code=404, detail=_("Setting not found"))
        return AdminSettingOut.model_validate(row, from_attributes=True)
    except HTTPException:
        raise
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.warning("Database schema not ready in get_admin_setting", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")


@router.put("/settings/{key}", name="update admin setting")
@traceroot.trace()
async def update_admin_setting(
    key: str,
    body: dict,
    session: Session = Depends(session),
    auth: Auth = Depends(require_admin),
):
    """Update (or create) an admin setting by key."""
    try:
        value = body.get("value")
        if value is None:
            raise HTTPException(status_code=400, detail="'value' is required")
        description = body.get("description", "")
        row = AdminSettings.set_value(session, key, str(value), description)
        logger.info("Admin setting updated", extra={"key": key, "value": value})
        return AdminSettingOut.model_validate(row, from_attributes=True)
    except HTTPException:
        raise
    except (ProgrammingError, OperationalError, InternalError) as e:
        logger.warning("Database schema not ready in update_admin_setting", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Database schema not ready. A migration may be pending.")


@router.get("/additional-fee", name="get additional fee (public)")
@traceroot.trace()
async def get_additional_fee(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """Public endpoint returning the current additional fee percentage."""
    try:
        fee = AdminSettings.get_additional_fee_percent(session)
        return {"additional_fee_percent": fee}
    except (ProgrammingError, OperationalError, InternalError):
        return {"additional_fee_percent": 5.0}
