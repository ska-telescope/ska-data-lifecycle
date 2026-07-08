"""Unit tests for trigger installation and external execution block handling."""
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@pytest.fixture(name="engine")
async def engine_fixture() -> AsyncGenerator[AsyncEngine, None]:
    """Create test suite scope async engine.

    Uses env DATABASE_URL to configure alternative engines.
    """
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(db_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(name="connection")
async def connection_fixture(engine):
    """Create a database connection for tests."""
    async with engine.connect() as connection:
        yield connection


async def _install_execution_schema(connection):
    raw_conn = (await connection.get_raw_connection()).driver_connection
    exection_schema_sql = """
        CREATE SCHEMA IF NOT EXISTS execution;
        CREATE TABLE execution.execution_blocks (
        id bigint PRIMARY KEY,
        parent_fk bigint,
        sbi_fk bigint GENERATED ALWAYS AS (parent_fk) STORED,
        data jsonb NOT NULL,
        version bigint DEFAULT 1,
        created_by text NOT NULL,
        created_on timestamptz NOT NULL DEFAULT current_timestamp,
        last_modified_on timestamptz NOT NULL DEFAULT current_timestamp,
        last_modified_by text NOT NULL);
    """
    await raw_conn.execute(exection_schema_sql)


async def _install_eb_trigger(connection):
    trigger_sql = (
        Path(__file__).resolve().parents[2] / "setup" / "DB" / "create-eb-data-item-trigger.sql"
    )
    raw_conn = (await connection.get_raw_connection()).driver_connection
    await raw_conn.execute(trigger_sql.read_text())


async def _drop_execution_schema(connection):
    raw_conn = (await connection.get_raw_connection()).driver_connection
    drop_schema_sql = """
        DROP SCHEMA IF EXISTS execution CASCADE;
    """
    await raw_conn.execute(drop_schema_sql)


@pytest.mark.asyncio
async def test_execution_block_eb_id_inserts_container_data_item(connection):
    """Install execution schema and trigger, then verify eb_id creates a container item."""
    try:
        async with connection.begin():
            await _install_execution_schema(connection)
            await _install_eb_trigger(connection)

            await connection.execute(
                text(
                    "INSERT INTO execution.execution_blocks "
                    "(id, parent_fk, data, created_by, last_modified_by) "
                    "VALUES (20, 10, '{\"eb_id\": \"eb-123\"}'::jsonb, 'pytest', 'pytest');"
                )
            )

            result = await connection.execute(
                text("SELECT item_name, item_type FROM dlm.data_item WHERE item_name = 'eb-123';")
            )
            rows = result.fetchall()
    finally:
        await _drop_execution_schema(connection)

    assert len(rows) == 1
    assert rows[0][0] == "eb-123"
    assert rows[0][1] == "container"
