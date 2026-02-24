#!/usr/bin/env python3
"""Seed the database from JSON fixture files.

Reads providers.json, pricing.json, and settings.json from the fixtures
directory and upserts rows into admin_llm_config, admin_model_pricing,
and admin_settings respectively.

Optionally loads API keys from fixtures/api_keys.json (gitignored).

Usage:
  # From hanggent/server/ directory:

  # Seed all tables (no API keys)
  python scripts/seed_from_fixtures.py

  # Seed with API keys
  python scripts/seed_from_fixtures.py --with-keys

  # Dry-run (preview changes without writing)
  python scripts/seed_from_fixtures.py --dry-run

  # Force overwrite existing rows
  python scripts/seed_from_fixtures.py --force --with-keys

  # Seed only specific tables
  python scripts/seed_from_fixtures.py --only providers pricing
"""
import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

# Ensure the server package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select
from app.component.database import engine
from app.model.admin.llm_config import (
    AdminLLMConfig,
    AdminModelPricing,
    ConfigStatus,
)
from app.model.admin.admin_settings import AdminSettings

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> list[dict]:
    """Load a fixture JSON file by name (without .json extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping")
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"  WARNING: {path} does not contain a JSON array, skipping")
        return []
    return data


def _load_api_keys() -> dict[str, str]:
    """Load API keys from fixtures/api_keys.json (gitignored)."""
    path = FIXTURES_DIR / "api_keys.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Strip the _comment entry
    return {k: v for k, v in data.items() if not k.startswith("_")}


def seed_providers(
    session: Session,
    *,
    with_keys: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Seed admin_llm_config from providers.json. Returns (created, updated, skipped)."""
    providers = _load_fixture("providers")
    if not providers:
        return 0, 0, 0

    api_keys = _load_api_keys() if with_keys else {}
    created, updated, skipped = 0, 0, 0

    for p in providers:
        name = p["provider_name"]
        existing = session.exec(
            select(AdminLLMConfig).where(AdminLLMConfig.provider_name == name)
        ).first()

        api_key = api_keys.get(name, "") if with_keys else ""

        if existing:
            if not force:
                skipped += 1
                if not dry_run:
                    # Still update API key if provided and currently empty
                    if with_keys and api_key and not existing.api_key:
                        existing.api_key = api_key
                        session.add(existing)
                        updated += 1
                        skipped -= 1
                print(f"  {'[DRY] ' if dry_run else ''}~ '{name}' {'skipped (exists)' if skipped > updated else 'key updated'}")
                continue
            # Force update: overwrite all fields
            existing.display_name = p.get("display_name", existing.display_name)
            existing.endpoint_url = p.get("endpoint_url", existing.endpoint_url)
            existing.model_type = p.get("model_type", existing.model_type)
            existing.extra_config = p.get("extra_config", existing.extra_config)
            existing.status = ConfigStatus(p.get("status", 1))
            existing.priority = p.get("priority", existing.priority)
            existing.rate_limit_rpm = p.get("rate_limit_rpm", existing.rate_limit_rpm)
            existing.rate_limit_tpm = p.get("rate_limit_tpm", existing.rate_limit_tpm)
            existing.notes = p.get("notes", existing.notes)
            if with_keys and api_key:
                existing.api_key = api_key
            if not dry_run:
                session.add(existing)
            updated += 1
            print(f"  {'[DRY] ' if dry_run else ''}⟳ '{name}' updated (force)")
        else:
            config = AdminLLMConfig(
                provider_name=name,
                display_name=p.get("display_name", ""),
                endpoint_url=p.get("endpoint_url", ""),
                model_type=p.get("model_type", ""),
                api_key=api_key,
                extra_config=p.get("extra_config"),
                status=ConfigStatus(p.get("status", 1)),
                priority=p.get("priority", 0),
                rate_limit_rpm=p.get("rate_limit_rpm"),
                rate_limit_tpm=p.get("rate_limit_tpm"),
                notes=p.get("notes", ""),
            )
            if not dry_run:
                session.add(config)
            created += 1
            print(f"  {'[DRY] ' if dry_run else ''}+ '{name}' created")

    return created, updated, skipped


def seed_pricing(
    session: Session,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Seed admin_model_pricing from pricing.json. Returns (created, updated, skipped)."""
    entries = _load_fixture("pricing")
    if not entries:
        return 0, 0, 0

    created, updated, skipped = 0, 0, 0

    for p in entries:
        provider = p["provider_name"]
        model = p["model_name"]
        existing = session.exec(
            select(AdminModelPricing).where(
                AdminModelPricing.provider_name == provider,
                AdminModelPricing.model_name == model,
            )
        ).first()

        if existing:
            if not force:
                skipped += 1
                print(f"  {'[DRY] ' if dry_run else ''}~ '{provider}/{model}' skipped (exists)")
                continue
            existing.display_name = p.get("display_name", existing.display_name)
            existing.input_price_per_million = Decimal(p["input_price_per_million"])
            existing.output_price_per_million = Decimal(p["output_price_per_million"])
            existing.cost_tier = p.get("cost_tier", existing.cost_tier)
            existing.context_length = p.get("context_length", existing.context_length)
            existing.is_available = p.get("is_available", existing.is_available)
            existing.notes = p.get("notes", existing.notes)
            if not dry_run:
                session.add(existing)
            updated += 1
            print(f"  {'[DRY] ' if dry_run else ''}⟳ '{provider}/{model}' updated (force)")
        else:
            pricing = AdminModelPricing(
                provider_name=provider,
                model_name=model,
                display_name=p.get("display_name", ""),
                input_price_per_million=Decimal(p["input_price_per_million"]),
                output_price_per_million=Decimal(p["output_price_per_million"]),
                cost_tier=p.get("cost_tier", "standard"),
                context_length=p.get("context_length"),
                is_available=p.get("is_available", True),
                notes=p.get("notes", ""),
            )
            if not dry_run:
                session.add(pricing)
            created += 1
            print(f"  {'[DRY] ' if dry_run else ''}+ '{provider}/{model}' created")

    return created, updated, skipped


def seed_settings(
    session: Session,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Seed admin_settings from settings.json. Returns (created, updated, skipped)."""
    entries = _load_fixture("settings")
    if not entries:
        return 0, 0, 0

    created, updated, skipped = 0, 0, 0

    for s in entries:
        key = s["key"]
        existing = session.exec(
            select(AdminSettings).where(AdminSettings.key == key)
        ).first()

        if existing:
            if not force:
                skipped += 1
                print(f"  {'[DRY] ' if dry_run else ''}~ '{key}' skipped (exists)")
                continue
            existing.value = s["value"]
            if s.get("description"):
                existing.description = s["description"]
            if not dry_run:
                session.add(existing)
            updated += 1
            print(f"  {'[DRY] ' if dry_run else ''}⟳ '{key}' updated (force)")
        else:
            setting = AdminSettings(
                key=key,
                value=s["value"],
                description=s.get("description", ""),
            )
            if not dry_run:
                session.add(setting)
            created += 1
            print(f"  {'[DRY] ' if dry_run else ''}+ '{key}' created")

    return created, updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed database from JSON fixture files")
    parser.add_argument(
        "--with-keys",
        action="store_true",
        help="Load API keys from fixtures/api_keys.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing rows (default: skip if exists)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to database",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["providers", "pricing", "settings"],
        help="Seed only specific tables (default: all)",
    )
    args = parser.parse_args()

    tables = args.only or ["providers", "pricing", "settings"]
    mode = "DRY-RUN" if args.dry_run else ("FORCE" if args.force else "normal")
    print(f"Seeding from fixtures (mode: {mode}, tables: {', '.join(tables)})...\n")

    if args.with_keys:
        keys_path = FIXTURES_DIR / "api_keys.json"
        if keys_path.exists():
            print(f"  Loading API keys from {keys_path}")
        else:
            print(f"  WARNING: {keys_path} not found — providers will have empty API keys")

    with Session(engine) as session:
        totals = {"created": 0, "updated": 0, "skipped": 0}

        if "providers" in tables:
            print("\n--- Providers (admin_llm_config) ---")
            c, u, s = seed_providers(
                session, with_keys=args.with_keys, force=args.force, dry_run=args.dry_run,
            )
            totals["created"] += c
            totals["updated"] += u
            totals["skipped"] += s

        if "pricing" in tables:
            print("\n--- Pricing (admin_model_pricing) ---")
            c, u, s = seed_pricing(session, force=args.force, dry_run=args.dry_run)
            totals["created"] += c
            totals["updated"] += u
            totals["skipped"] += s

        if "settings" in tables:
            print("\n--- Settings (admin_settings) ---")
            c, u, s = seed_settings(session, force=args.force, dry_run=args.dry_run)
            totals["created"] += c
            totals["updated"] += u
            totals["skipped"] += s

        if not args.dry_run and (totals["created"] or totals["updated"]):
            session.commit()
            print(f"\n✓ Committed: {totals['created']} created, {totals['updated']} updated, {totals['skipped']} skipped")
        elif args.dry_run:
            print(f"\n[DRY-RUN] Would: {totals['created']} create, {totals['updated']} update, {totals['skipped']} skip")
        else:
            print("\nNo changes needed")


if __name__ == "__main__":
    main()
