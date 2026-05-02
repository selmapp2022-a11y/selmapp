#!/usr/bin/env python3
"""
DigitalOcean / production migration runner.

Goals:
- Wait until Postgres is reachable (handles cold starts / networking delays)
- Apply Alembic migrations to bring schema to the latest revision(s)
- Avoid unsafe auto-stamping by default

Behavior:
- If `alembic_version` exists -> `alembic upgrade heads`
- If `alembic_version` does NOT exist:
  - If there are no existing tables -> new DB -> `alembic upgrade heads`
  - If tables already exist -> requires a one-time decision:
      - If AUTO_STAMP=1 -> `alembic stamp heads` then `alembic upgrade heads`
      - Else -> exit with a clear error (so deploy fails loudly)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure we can import `app.*` when running as a script
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.database import _build_asyncpg_url_and_connect_args  # noqa: E402


def _run_alembic(*args: str) -> None:
    """
    Run Alembic as a subprocess.

    Why subprocess?
    - Our Alembic env.py uses `asyncio.run(...)` for async migrations.
    - Calling Alembic programmatically from inside an existing event loop
      can raise: "asyncio.run() cannot be called from a running event loop".
    - Running the CLI in a subprocess avoids nested event loops and works
      reliably across platforms.
    """
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(BACKEND_DIR / "alembic.ini"),
        *args,
    ]
    subprocess.run(cmd, cwd=str(BACKEND_DIR), check=True)


async def _wait_for_db(timeout_seconds: int = 60, poll_seconds: float = 2.0) -> None:
    db_url, connect_args = _build_asyncpg_url_and_connect_args(settings.DATABASE_URL)
    engine = create_async_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    try:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return
            except Exception as e:  # noqa: BLE001
                last_error = e
                await asyncio.sleep(poll_seconds)
        raise RuntimeError(f"Database not reachable after {timeout_seconds}s: {last_error}") from last_error
    finally:
        await engine.dispose()


async def _db_state() -> tuple[bool, int, int]:
    """
    Returns:
      (has_alembic_version_table, non_alembic_table_count, public_enum_type_count)
    """
    db_url, connect_args = _build_asyncpg_url_and_connect_args(settings.DATABASE_URL)
    engine = create_async_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            # `to_regclass` returns NULL if the relation doesn't exist
            has_version = (
                (await conn.execute(text("SELECT to_regclass('public.alembic_version')")))
                .scalar_one()
                is not None
            )

            non_alembic_tables = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*)::int
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_type = 'BASE TABLE'
                          AND table_name <> 'alembic_version';
                        """
                    )
                )
            ).scalar_one()

            # Enum types are schema objects and can survive "drop tables" resets.
            # If enums exist but tables don't, migrations can still fail with:
            #   DuplicateObjectError: type "..."" already exists
            public_enum_types = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*)::int
                        FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.typtype = 'e'
                          AND n.nspname = 'public';
                        """
                    )
                )
            ).scalar_one()

            return has_version, int(non_alembic_tables), int(public_enum_types)
    finally:
        await engine.dispose()


def _upgrade_heads() -> None:
    # NOTE: Avoid emoji in logs (Windows cp1252 consoles will crash).
    print("Applying Alembic migrations: upgrade heads")
    _run_alembic("upgrade", "heads")
    print("OK: Database schema is up to date")


def _stamp_heads() -> None:
    # NOTE: Avoid emoji in logs (Windows cp1252 consoles will crash).
    print("Stamping database as up-to-date (heads)")
    _run_alembic("stamp", "heads")
    print("OK: Stamp complete")


async def main() -> int:
    # Default: be safe. Only stamp if the operator opts in.
    auto_stamp = os.getenv("AUTO_STAMP", "").strip().lower() in {"1", "true", "yes", "y"}

    await _wait_for_db()
    has_version, table_count, enum_count = await _db_state()

    if has_version:
        _upgrade_heads()
        return 0

    # No alembic_version table yet
    if table_count == 0 and enum_count == 0:
        # Fresh DB, safe to run migrations normally
        _upgrade_heads()
        return 0

    # No tables but enums exist -> incomplete reset (types weren't dropped)
    if table_count == 0 and enum_count > 0:
        print(
            "\n".join(
                [
                    "ERROR: Database has no tables but still has PostgreSQL enum types in schema 'public'.",
                    "This usually happens when tables were deleted but enum types were not (Postgres enums are not tables).",
                    "",
                    "Fix (recommended): drop and recreate the public schema (DELETES ALL DATA):",
                    "  DROP SCHEMA IF EXISTS public CASCADE;",
                    "  CREATE SCHEMA public;",
                    "  GRANT ALL ON SCHEMA public TO public;",
                    "",
                    "Then rerun this job.",
                    "",
                    "Note: AUTO_STAMP is NOT appropriate here because it would skip migrations and leave the DB empty.",
                ]
            )
        )
        return 2

    # Existing schema but no Alembic tracking (common if create_all() was used)
    if auto_stamp:
        _stamp_heads()
        _upgrade_heads()
        return 0

    print(
        "\n".join(
            [
                "ERROR: Database already has tables but has no alembic_version table.",
                "This usually means the schema was created outside Alembic (e.g. create_all()).",
                "",
                "Choose ONE of these options:",
                "  1) One-time (recommended if schema matches current code):",
                "     python -m alembic -c alembic.ini stamp heads",
                "     python -m alembic -c alembic.ini upgrade heads",
                "",
                "  2) Automatic (dangerous if schema doesn't match): set AUTO_STAMP=1 for this job.",
                "",
                "  3) Recreate the database (dev-only): drop schema/database then run upgrade.",
            ]
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))







