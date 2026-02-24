#!/usr/bin/env python3
"""Seed the admin_llm_config table with default cloud providers.

Usage:
  # From the hanggent/server directory:
  python scripts/seed_admin_providers.py

  # With a specific provider and key:
  python scripts/seed_admin_providers.py --provider openai --api-key sk-xxx

  # Seed all default providers (prompts for keys):
  python scripts/seed_admin_providers.py --all

  # Non-interactive mode (skip providers without keys):
  python scripts/seed_admin_providers.py --all --non-interactive
"""
import argparse
import os
import sys

# Ensure the server package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select
from app.component.database import engine
from app.model.admin.llm_config import AdminLLMConfig, ConfigStatus, DEFAULT_PROVIDERS


def seed_provider(
    session: Session,
    provider_name: str,
    api_key: str,
    display_name: str = "",
    endpoint_url: str = "",
    model_type: str = "",
) -> bool:
    """Insert or update an admin LLM config row. Returns True if a change was made."""
    existing = session.exec(
        select(AdminLLMConfig).where(AdminLLMConfig.provider_name == provider_name)
    ).first()

    if existing:
        if existing.api_key == api_key and existing.status == ConfigStatus.enabled:
            print(f"  ✓ '{provider_name}' already configured and enabled — skipped")
            return False
        existing.api_key = api_key
        existing.status = ConfigStatus.enabled
        if display_name:
            existing.display_name = display_name
        if endpoint_url:
            existing.endpoint_url = endpoint_url
        session.add(existing)
        print(f"  ⟳ '{provider_name}' updated with new key")
    else:
        config = AdminLLMConfig(
            provider_name=provider_name,
            display_name=display_name or provider_name,
            api_key=api_key,
            endpoint_url=endpoint_url,
            model_type=model_type,
            status=ConfigStatus.enabled,
            priority=0,
        )
        session.add(config)
        print(f"  + '{provider_name}' created")

    return True


def main():
    parser = argparse.ArgumentParser(description="Seed admin LLM provider configs")
    parser.add_argument("--provider", help="Single provider name to seed (e.g. openai)")
    parser.add_argument("--api-key", help="API key for the provider")
    parser.add_argument("--all", action="store_true", help="Seed all default providers")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip providers that don't have keys set via env vars",
    )
    args = parser.parse_args()

    # Environment variable mapping: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
    env_key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "together": "TOGETHER_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "hanggent": "HANGGENT_API_KEY",
    }

    if not args.provider and not args.all:
        parser.print_help()
        sys.exit(1)

    with Session(engine) as session:
        changed = False

        if args.provider:
            api_key = args.api_key or os.environ.get(env_key_map.get(args.provider, ""), "")
            if not api_key:
                api_key = input(f"Enter API key for '{args.provider}': ").strip()
            if not api_key:
                print(f"  ✗ No API key provided for '{args.provider}' — skipped")
                sys.exit(1)

            # Find matching default for endpoint/display info
            default = next(
                (d for d in DEFAULT_PROVIDERS if d["provider_name"] == args.provider),
                {},
            )
            changed = seed_provider(
                session,
                args.provider,
                api_key,
                display_name=default.get("display_name", ""),
                endpoint_url=default.get("endpoint_url", ""),
                model_type=default.get("model_type", ""),
            )

        elif args.all:
            print("Seeding all default providers...\n")
            for default in DEFAULT_PROVIDERS:
                name = default["provider_name"]
                env_var = env_key_map.get(name, "")
                api_key = os.environ.get(env_var, "") if env_var else ""

                if not api_key and not args.non_interactive:
                    api_key = input(
                        f"Enter API key for '{name}' (env: {env_var}, leave blank to skip): "
                    ).strip()

                if not api_key:
                    print(f"  – '{name}' skipped (no key)")
                    continue

                if seed_provider(
                    session,
                    name,
                    api_key,
                    display_name=default.get("display_name", ""),
                    endpoint_url=default.get("endpoint_url", ""),
                    model_type=default.get("model_type", ""),
                ):
                    changed = True

        if changed:
            session.commit()
            print("\n✓ Database updated successfully")
        else:
            print("\nNo changes needed")


if __name__ == "__main__":
    main()
