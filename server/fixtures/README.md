# Seed Data Fixtures

This directory contains JSON fixture files used to seed the Hanggent Cloud admin database tables for model provider configurations, pricing, and settings.

## Files

| File | Description | Committed? |
|------|-------------|------------|
| `providers.json` | `admin_llm_config` rows (provider configs without API keys) | Yes |
| `pricing.json` | `admin_model_pricing` rows (per-model token pricing) | Yes |
| `settings.json` | `admin_settings` rows (e.g. additional fee percent) | Yes |
| `api_keys.json.example` | Template for provider API keys | Yes |
| `api_keys.json` | **Real API keys** — gitignored, never commit! | **No** |

## Usage

### Export from production

```bash
# From hanggent/server/ directory
python scripts/export_seed_data.py --namespace hanggent
```

This connects to the production PostgreSQL pod via `kubectl exec` and writes updated fixture files here.

### Import into a database

```bash
# Seed providers + pricing + settings (no API keys)
python scripts/seed_from_fixtures.py

# Seed with API keys from api_keys.json
python scripts/seed_from_fixtures.py --with-keys

# Dry-run (preview without writing)
python scripts/seed_from_fixtures.py --dry-run

# Force overwrite existing rows
python scripts/seed_from_fixtures.py --force --with-keys
```
