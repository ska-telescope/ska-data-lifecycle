"""Tests for heuristic worker coordination."""

import asyncio
import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from ska_dlm.dlm_db import create_async_sql_engine
from ska_dlm.dlm_heuristics import dlm_heuristics
from ska_dlm.dlm_heuristics.dlm_heuristics import heuristic_worker_lock


@pytest.mark.asyncio
@pytest.mark.parametrize("acquired", [True, False])
async def test_worker_lock_releases_only_when_acquired(acquired):
    """Only a worker holding the advisory lock releases it."""
    connection = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = acquired
    connection.execute.return_value = result
    engine = MagicMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

    async with heuristic_worker_lock(engine) as locked:
        assert locked is acquired

    assert connection.execute.await_count == (2 if acquired else 1)
    assert connection.commit.await_count == (2 if acquired else 1)
    if acquired:
        assert "pg_advisory_unlock" in str(connection.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_worker_lock_releases_on_error():
    """A failing heuristic cannot leave its lock held in the pool."""
    connection = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = True
    connection.execute.return_value = result
    engine = MagicMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

    with pytest.raises(RuntimeError):
        async with heuristic_worker_lock(engine):
            raise RuntimeError("failed")

    assert connection.execute.await_count == 2
    assert "pg_advisory_unlock" in str(connection.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_worker_lock_invalidates_connection_if_unlock_fails():
    """A potentially locked connection is not returned to the pool."""
    connection = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = True
    connection.execute.side_effect = [result, RuntimeError("unlock failed")]
    engine = MagicMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

    with pytest.raises(RuntimeError, match="unlock failed"):
        async with heuristic_worker_lock(engine):
            pass

    connection.invalidate.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("worker", "expected"),
    [
        ("expiry", ["UidExpiryHeuristic", "OidExpiryHeuristic"]),
        ("storage", ["UpdateStorageUsageHeuristic", "HighWaterMarkHeuristic"]),
        (
            "all",
            [
                "UidExpiryHeuristic",
                "OidExpiryHeuristic",
                "UpdateStorageUsageHeuristic",
                "HighWaterMarkHeuristic",
            ],
        ),
    ],
)
async def test_worker_cycle_runs_selected_heuristics_in_order(monkeypatch, worker, expected):
    """Each role runs its own heuristics in dependency order."""
    calls = []
    for name in expected:
        heuristic = MagicMock()
        heuristic.__name__ = name
        heuristic.return_value.execute = AsyncMock(
            return_value=MagicMock(success=True, message="ok")
        )
        heuristic.side_effect = (
            lambda session, name=name, instance=heuristic.return_value: calls.append(name)
            or instance
        )
        monkeypatch.setattr(dlm_heuristics, name, heuristic)

    session = AsyncMock()
    monkeypatch.setattr(dlm_heuristics, "create_async_sql_session", lambda engine: session)
    await dlm_heuristics._run_heuristic_cycle(MagicMock(), worker)

    assert calls == expected
    assert session.__aenter__.await_count == len(expected)
    assert session.__aenter__.return_value.commit.await_count == len(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("leader,acquired", [(False, False), (True, False), (True, True)])
async def test_worker_runs_only_with_both_locks(monkeypatch, leader, acquired):
    """Standby and contending workers do not execute heuristics."""
    stop_event = asyncio.Event()
    lock_ids = []

    @asynccontextmanager
    async def engine_context(_url):
        yield object()

    @asynccontextmanager
    async def lock_context(_engine, lock_id=1):
        lock_ids.append(lock_id)
        yield leader if lock_id != 1 else acquired

    async def stop_waiting(_event, _timeout):
        stop_event.set()

    run_cycle = AsyncMock()
    monkeypatch.setattr(dlm_heuristics, "HEURISTIC_WORKER", "expiry")
    monkeypatch.setattr(dlm_heuristics, "create_async_sql_engine", engine_context)
    monkeypatch.setattr(dlm_heuristics, "heuristic_worker_lock", lock_context)
    monkeypatch.setattr(dlm_heuristics, "_wait_for_stop", stop_waiting)
    monkeypatch.setattr(dlm_heuristics, "_run_heuristic_cycle", run_cycle)

    await dlm_heuristics.heuristic_process_loop(stop_event)

    assert lock_ids == ([3, 1] if leader else [3])
    assert run_cycle.await_count == int(leader and acquired)


@pytest.mark.asyncio
async def test_worker_rejects_unknown_role(monkeypatch):
    """Invalid worker configuration fails before opening a database connection."""
    monkeypatch.setattr(dlm_heuristics, "HEURISTIC_WORKER", "invalid")
    with pytest.raises(ValueError, match="Unknown heuristic worker"):
        await dlm_heuristics.heuristic_process_loop(asyncio.Event())


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("DLM_TEST_WORKER_POSTGRES_URL"), reason="PostgreSQL worker test URL not set"
)
async def test_worker_locks_contend_and_release_in_postgresql():
    """Independent database connections exclude each other and allow takeover."""
    async with create_async_sql_engine(os.environ["DLM_TEST_WORKER_POSTGRES_URL"]) as first:
        async with create_async_sql_engine(os.environ["DLM_TEST_WORKER_POSTGRES_URL"]) as second:
            async with heuristic_worker_lock(first, 3) as acquired:
                assert acquired
                async with heuristic_worker_lock(second, 3) as contender:
                    assert not contender
                async with heuristic_worker_lock(second, 4) as different_role:
                    assert different_role
            async with heuristic_worker_lock(second, 3) as takeover:
                assert takeover
