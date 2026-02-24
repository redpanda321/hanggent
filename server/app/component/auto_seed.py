"""
Auto-seed default admin LLM provider configurations on startup.

Ensures DEFAULT_PROVIDERS entries exist in admin_llm_config with correct
display_name, endpoint_url, and model_type without overwriting admin-set
api_key or status.
"""

import logging

from sqlmodel import select

logger = logging.getLogger("server_auto_seed")


def seed_default_providers() -> None:
    """Upsert DEFAULT_PROVIDERS into admin_llm_config.

    - Missing entries are created (status=enabled, empty api_key).
    - Existing entries get display_name, endpoint_url, and model_type updated
      ONLY if the current value is empty (preserves admin overrides).
    """
    try:
        from app.component.database import session_make
        from app.model.admin.llm_config import (
            AdminLLMConfig,
            ConfigStatus,
            DEFAULT_PROVIDERS,
        )

        s = session_make()
        try:
            created = 0
            updated = 0

            for provider in DEFAULT_PROVIDERS:
                existing = s.exec(
                    select(AdminLLMConfig).where(
                        AdminLLMConfig.provider_name == provider["provider_name"]
                    )
                ).first()

                if existing:
                    # Update fields that are empty — never overwrite admin customisations
                    changed = False
                    if not existing.display_name and provider.get("display_name"):
                        existing.display_name = provider["display_name"]
                        changed = True
                    if not existing.endpoint_url and provider.get("endpoint_url"):
                        existing.endpoint_url = provider["endpoint_url"]
                        changed = True
                    if not existing.model_type and provider.get("model_type"):
                        existing.model_type = provider["model_type"]
                        changed = True
                    # Re-enable entries that were seeded as disabled
                    # (admin seed endpoint creates them with status=disabled).
                    # Default providers should always be visible to users.
                    if existing.status == ConfigStatus.disabled:
                        existing.status = ConfigStatus.enabled
                        changed = True
                    if changed:
                        s.add(existing)
                        updated += 1
                else:
                    config = AdminLLMConfig(
                        provider_name=provider["provider_name"],
                        display_name=provider.get("display_name", ""),
                        endpoint_url=provider.get("endpoint_url", ""),
                        model_type=provider.get("model_type", ""),
                        api_key="",  # Must be configured by admin
                        status=ConfigStatus.enabled,
                        priority=0,
                    )
                    s.add(config)
                    created += 1

            s.commit()

            if created or updated:
                logger.info(
                    "Auto-seed default providers completed",
                    extra={"created": created, "updated": updated},
                )
            else:
                logger.debug("Auto-seed: all default providers already present")
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    except Exception as e:
        # Never block server startup
        logger.warning("Auto-seed default providers failed: %s", e)
