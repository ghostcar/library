"""Integration test: Alembic migration applies cleanly on a fresh database."""

from __future__ import annotations

import asyncio
import random
import string
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from tests.conftest import get_test_database_url

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _parse_url(url: str) -> dict[str, str]:
    # postgresql+asyncpg://user:pass@host:port/db
    without_proto = url.split("://", 1)[1]
    creds, rest = without_proto.rsplit("@", 1)
    user, password = creds.split(":", 1)
    hostport, database = rest.split("/", 1)
    host, port = hostport.split(":", 1)
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": database,
    }


async def _create_database(base: dict[str, str], name: str) -> None:
    conn = await asyncpg.connect(
        user=base["user"],
        password=base["password"],
        host=base["host"],
        port=int(base["port"]),
        database=base["database"],
    )
    try:
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


async def _drop_database(base: dict[str, str], name: str) -> None:
    conn = await asyncpg.connect(
        user=base["user"],
        password=base["password"],
        host=base["host"],
        port=int(base["port"]),
        database=base["database"],
    )
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "  # noqa: S608
            f"WHERE datname = '{name}' AND pid <> pg_backend_pid()",
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        await conn.close()


def test_migration_upgrade_head_on_fresh_database() -> None:
    base = _parse_url(get_test_database_url())
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))  # noqa: S311
    temp_db = f"library_migrate_{suffix}"
    url = (
        f"postgresql+asyncpg://{base['user']}:{base['password']}"
        f"@{base['host']}:{base['port']}/{temp_db}"
    )

    async def setup() -> None:
        await _create_database(base, temp_db)

    async def teardown() -> None:
        await _drop_database(base, temp_db)

    asyncio.run(setup())
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "alembic", "-x", f"database_url={url}", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, f"alembic failed:\n{result.stdout}\n{result.stderr}"

        async def verify() -> list[str]:
            conn = await asyncpg.connect(
                user=base["user"],
                password=base["password"],
                host=base["host"],
                port=int(base["port"]),
                database=temp_db,
            )
            try:
                rows = await conn.fetch(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name",
                )
                version = await conn.fetchval("SELECT version_num FROM alembic_version")
                assert version == "0009"
                return [r["table_name"] for r in rows]
            finally:
                await conn.close()

        tables = asyncio.run(verify())
        expected = {
            "alembic_version",
            "ai_corrections",
            "ai_proposals",
            "api_tokens",
            "assets",
            "asset_relations",
            "audit_log",
            "author_aliases",
            "authors",
            "duplicate_candidates",
            "import_batches",
            "import_items",
            "jobs",
            "notifications",
            "normalization_runs",
            "outbox_events",
            "reading_state_history",
            "reading_states",
            "series_user_states",
            "source_observations",
            "watch_rules",
            "series",
            "series_aliases",
            "series_memberships",
            "source_author_records",
            "source_records",
            "users",
            "work_authors",
            "works",
        }
        assert set(tables) == expected
    finally:
        asyncio.run(teardown())
