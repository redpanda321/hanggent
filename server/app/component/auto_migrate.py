"""
Automatic database migration utility for server startup.

Runs Alembic migrations to ensure the database schema is up to date.
"""

import os
import sys
import pathlib

# Ensure project root is in path
_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("server_auto_migrate")

# server/ directory — where alembic.ini and alembic/ live
_server_dir = pathlib.Path(__file__).parent.parent.parent


def run_migrations() -> bool:
    """
    Run Alembic migrations to upgrade database to the latest version.
    
    Returns:
        True if migrations ran successfully or were already up to date.
        False if an error occurred.
    """
    # Check if auto-migration is disabled
    if os.environ.get("DISABLE_AUTO_MIGRATE", "").lower() in ("true", "1", "yes"):
        logger.info("Auto-migration disabled via DISABLE_AUTO_MIGRATE env var")
        return True

    try:
        from alembic.config import Config
        from alembic import command
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine
        
        from app.component.environment import env
        
        # Get database URL
        database_url = env("database_url")
        if not database_url:
            logger.warning("No database_url configured, skipping auto-migration")
            return True
        
        # Resolve alembic.ini from the server directory
        # __file__ = server/app/component/auto_migrate.py
        # _server_dir = server/  (3 levels up)
        alembic_ini = _server_dir / "alembic.ini"
        
        if not alembic_ini.exists():
            logger.warning(f"alembic.ini not found at {alembic_ini}, skipping auto-migration")
            return True
        
        # Create Alembic config
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        
        # Ensure script_location is resolved relative to the server directory
        # (alembic.ini has script_location = alembic, which is relative to CWD)
        script_location = alembic_cfg.get_main_option("script_location")
        if script_location and not os.path.isabs(script_location):
            resolved = str(_server_dir / script_location)
            alembic_cfg.set_main_option("script_location", resolved)
            logger.debug(f"Resolved script_location: {script_location} -> {resolved}")
        
        # Check current revision
        engine = create_engine(database_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
        engine.dispose()
        
        # Get head revision
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        
        if current_rev == head_rev:
            logger.info(f"Database schema is up to date (revision: {current_rev})")
            return True
        
        logger.info(
            f"Running database migrations: {current_rev or 'none'} -> {head_rev}"
        )
        
        # Run upgrade
        command.upgrade(alembic_cfg, "head")
        
        # Verify the migration succeeded
        with create_engine(database_url).connect() as conn:
            context = MigrationContext.configure(conn)
            new_rev = context.get_current_revision()
        
        if new_rev == head_rev:
            logger.info(f"Database migrations completed successfully (now at: {head_rev})")
        else:
            logger.warning(
                f"Migration ran but revision mismatch: expected {head_rev}, got {new_rev}"
            )
        
        return True
        
    except ImportError as e:
        logger.warning(f"Alembic not available, skipping auto-migration: {e}")
        return True
    except Exception as e:
        logger.error(f"Auto-migration failed: {e}", exc_info=True)
        # Don't block server startup, but log the error prominently
        return False


def check_critical_columns() -> dict:
    """
    Check if critical database columns exist.
    
    Returns a dict with column names and their presence status.
    Useful for diagnosing migration issues.
    """
    try:
        from sqlalchemy import create_engine, inspect
        from app.component.environment import env
        
        database_url = env("database_url")
        if not database_url:
            return {"error": "No DATABASE_URL configured"}
        
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        # Check user table columns
        user_columns = {col["name"] for col in inspector.get_columns("user")}
        
        critical_columns = {
            "clerk_id": "clerk_id" in user_columns,
            "stripe_customer_id": "stripe_customer_id" in user_columns,
            "spending_limit": "spending_limit" in user_columns,
        }
        
        # Check if critical tables exist
        tables = inspector.get_table_names()
        critical_columns["refresh_token_table"] = "refresh_token" in tables
        critical_columns["user_usage_summary_table"] = "user_usage_summary" in tables
        
        return critical_columns
        
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Allow running directly to check/apply migrations
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration utility")
    parser.add_argument("--check", action="store_true", help="Check column status only")
    parser.add_argument("--migrate", action="store_true", help="Run migrations")
    args = parser.parse_args()
    
    if args.check:
        result = check_critical_columns()
        print("Critical columns status:")
        for col, status in result.items():
            print(f"  {col}: {status}")
    elif args.migrate:
        success = run_migrations()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
