#!/usr/bin/env python3
"""Export production seed data from the Vultr K8s PostgreSQL database.

Connects via ``kubectl exec`` to the PostgreSQL pod and exports the
``admin_llm_config``, ``admin_model_pricing``, and ``admin_settings``
tables as JSON fixture files suitable for seeding other environments.

API keys in ``admin_llm_config`` are **stripped** (replaced with empty
strings) so that the fixture files are safe to commit to version control.

Usage:
  # Export from production (default namespace: hanggent)
  python scripts/export_seed_data.py

  # Export from staging
  python scripts/export_seed_data.py --namespace hanggent-staging

  # Custom kubeconfig
  python scripts/export_seed_data.py --kubeconfig /path/to/kubeconfig

  # Custom output directory
  python scripts/export_seed_data.py --output-dir ./my-fixtures
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

# SQL queries to export each table as JSON
_QUERIES = {
    "providers": """
        SELECT json_agg(
            json_build_object(
                'provider_name', provider_name,
                'display_name', display_name,
                'endpoint_url', endpoint_url,
                'model_type', COALESCE(model_type, ''),
                'extra_config', extra_config,
                'status', status,
                'priority', priority,
                'rate_limit_rpm', rate_limit_rpm,
                'rate_limit_tpm', rate_limit_tpm,
                'notes', COALESCE(notes, '')
            ) ORDER BY provider_name
        )
        FROM admin_llm_config;
    """,
    "pricing": """
        SELECT json_agg(
            json_build_object(
                'provider_name', provider_name,
                'model_name', model_name,
                'display_name', display_name,
                'input_price_per_million', input_price_per_million::text,
                'output_price_per_million', output_price_per_million::text,
                'cost_tier', cost_tier,
                'context_length', context_length,
                'is_available', is_available,
                'notes', COALESCE(notes, '')
            ) ORDER BY provider_name, model_name
        )
        FROM admin_model_pricing;
    """,
    "settings": """
        SELECT json_agg(
            json_build_object(
                'key', key,
                'value', value,
                'description', COALESCE(description, '')
            ) ORDER BY key
        )
        FROM admin_settings;
    """,
}


def _kubectl_exec_psql(
    query: str,
    *,
    namespace: str = "hanggent",
    deployment: str = "postgres",
    db_user: str = "hanggent",
    db_name: str = "hanggent",
    kubeconfig: str | None = None,
) -> str:
    """Run a psql query via kubectl exec and return the raw stdout."""
    cmd = ["kubectl"]
    if kubeconfig:
        cmd += ["--kubeconfig", kubeconfig]
    cmd += [
        "exec",
        "-n", namespace,
        f"deploy/{deployment}",
        "--",
        "psql",
        "-U", db_user,
        "-d", db_name,
        "-t",   # tuples only (no headers)
        "-A",   # unaligned output
        "-c", query.strip(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"ERROR: kubectl exec failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def _generate_api_keys_example(providers: list[dict]) -> dict:
    """Build an api_keys.json.example from the exported providers."""
    example: dict = {
        "_comment": "Copy this file to api_keys.json and fill in real API keys. api_keys.json is gitignored.",
    }
    for p in providers:
        example[p["provider_name"]] = ""
    return example


def export(
    *,
    namespace: str,
    deployment: str,
    db_user: str,
    db_name: str,
    kubeconfig: str | None,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, query in _QUERIES.items():
        print(f"  Exporting {name}...", end=" ")
        raw = _kubectl_exec_psql(
            query,
            namespace=namespace,
            deployment=deployment,
            db_user=db_user,
            db_name=db_name,
            kubeconfig=kubeconfig,
        )
        if not raw or raw.lower() == "null":
            print(f"WARNING: table returned no rows for '{name}'")
            data: list = []
        else:
            data = json.loads(raw)

        out_path = output_dir / f"{name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"{len(data)} rows -> {out_path}")

    # Generate api_keys.json.example from exported providers
    providers_path = output_dir / "providers.json"
    if providers_path.exists():
        with open(providers_path, encoding="utf-8") as f:
            providers = json.load(f)
        example = _generate_api_keys_example(providers)
        example_path = output_dir / "api_keys.json.example"
        with open(example_path, "w", encoding="utf-8") as f:
            json.dump(example, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  api_keys.json.example updated ({len(providers)} providers)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export production admin seed data from Vultr K8s PostgreSQL"
    )
    parser.add_argument(
        "--namespace", "-n",
        default="hanggent",
        help="K8s namespace (default: hanggent, use hanggent-staging for staging)",
    )
    parser.add_argument(
        "--deployment",
        default="postgres",
        help="K8s deployment name for PostgreSQL (default: postgres)",
    )
    parser.add_argument(
        "--db-user",
        default="hanggent",
        help="PostgreSQL user (default: hanggent)",
    )
    parser.add_argument(
        "--db-name",
        default="hanggent",
        help="PostgreSQL database name (default: hanggent)",
    )
    parser.add_argument(
        "--kubeconfig",
        default=os.environ.get("KUBECONFIG"),
        help="Path to kubeconfig file (default: $KUBECONFIG or kubectl default)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=FIXTURES_DIR,
        help=f"Output directory for fixture files (default: {FIXTURES_DIR})",
    )
    args = parser.parse_args()

    print(f"Exporting seed data from namespace '{args.namespace}'...")
    export(
        namespace=args.namespace,
        deployment=args.deployment,
        db_user=args.db_user,
        db_name=args.db_name,
        kubeconfig=args.kubeconfig,
        output_dir=args.output_dir,
    )
    print("\nDone! Fixture files written to:", args.output_dir)
    print("NOTE: API keys are NOT included. Use fixtures/api_keys.json for keys.")


if __name__ == "__main__":
    main()
