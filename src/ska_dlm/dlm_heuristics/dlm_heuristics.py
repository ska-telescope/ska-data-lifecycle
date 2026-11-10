# pylint: disable=R0914,R0915
"""Heuristic engine daemon using SQLAlchemy ORM (asyncio)."""

import asyncio
import logging
import os
import random
import signal
import time
from contextlib import asynccontextmanager

from sqlalchemy import text

from ska_dlm.dlm_db import create_async_sql_engine, create_async_sql_session
from ska_dlm.dlm_heuristics.heuristics import (
    HighWaterMarkHeuristic,
    OidExpiryHeuristic,
    UidExpiryHeuristic,
    UpdateStorageUsageHeuristic,
)

logger = logging.getLogger(__name__)

HEURISTIC_DATABASE_URL = os.getenv(
    "DLM_HEURISTIC_DATABASE_URL",
    os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://ska_dlm_admin:password@dlm_db:5432/ska_dlm_testing"
    ),
)
HEURISTIC_POLL_INTERVAL = int(os.getenv("DLM_HEURISTIC_POLL_INTERVAL", "10"))
HEURISTIC_WORKER = os.getenv("DLM_HEURISTIC_WORKER", "all")
WORKER_LOCK_IDS = {"all": 2, "expiry": 3, "storage": 4}


@asynccontextmanager
async def heuristic_worker_lock(engine, lock_id=1):
    """Hold the database-wide heuristic lock on a dedicated connection."""
    async with engine.connect() as connection:
        try:
            result = await connection.execute(
                text("SELECT pg_try_advisory_lock(:namespace, :lock_id)"),
                {"namespace": 1397440844, "lock_id": lock_id},
            )
            acquired = result.scalar_one()
            await connection.commit()
        except BaseException:
            await connection.invalidate()
            raise
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:namespace, :lock_id)"),
                        {"namespace": 1397440844, "lock_id": lock_id},
                    )
                    await connection.commit()
                except BaseException:
                    await connection.invalidate()
                    raise


async def _wait_for_stop(stop_event, timeout):
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass


async def _run_heuristic_cycle(engine, worker):
    heuristics = []
    if worker in ("all", "expiry"):
        heuristics.extend((UidExpiryHeuristic, OidExpiryHeuristic))
    if worker in ("all", "storage"):
        heuristics.extend((UpdateStorageUsageHeuristic, HighWaterMarkHeuristic))

    for heuristic in heuristics:
        async with create_async_sql_session(engine) as session:
            result = await heuristic(session).execute()
            await session.commit()
        logger.info("%s returned: %s", heuristic.__name__, result.message)
        if not result.success:
            logger.warning("%s failed: %s", heuristic.__name__, result.data)


async def heuristic_process_loop(stop_event: asyncio.Event):
    """Run the configured heuristic worker until the stop event is set."""
    worker = HEURISTIC_WORKER
    if worker not in WORKER_LOCK_IDS:
        raise ValueError(
            f"Unknown heuristic worker {worker!r}; choose from {list(WORKER_LOCK_IDS)}"
        )
    if HEURISTIC_POLL_INTERVAL <= 0:
        raise ValueError("DLM_HEURISTIC_POLL_INTERVAL must be positive")

    async with create_async_sql_engine(HEURISTIC_DATABASE_URL) as engine:
        while not stop_event.is_set():
            try:
                async with heuristic_worker_lock(engine, WORKER_LOCK_IDS[worker]) as leader:
                    if leader:
                        logger.info("Heuristic worker %s acquired leadership", worker)
                        while not stop_event.is_set():
                            start = time.monotonic()
                            async with heuristic_worker_lock(engine) as acquired:
                                if acquired:
                                    await _run_heuristic_cycle(engine, worker)
                            if acquired:
                                delay = max(
                                    0.5, HEURISTIC_POLL_INTERVAL - (time.monotonic() - start)
                                )
                            else:
                                delay = random.uniform(0.1, 0.5)
                            await _wait_for_stop(stop_event, delay)
            except asyncio.CancelledError:
                raise
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Heuristic worker %s failed; retrying", worker)
            if not stop_event.is_set():
                await _wait_for_stop(stop_event, HEURISTIC_POLL_INTERVAL)


def _configure_signals(stop_event: asyncio.Event):
    def _handler(*_):
        logger.info("Signal received: stopping heuristic engine")
        stop_event.set()

    signal.signal(signal.SIGINT, lambda sig, frame: _handler())
    signal.signal(signal.SIGTERM, lambda sig, frame: _handler())


def main() -> None:
    """Entrypoint for the heuristic engine process."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Starting DLM heuristic engine")

    stop_event = asyncio.Event()
    _configure_signals(stop_event)

    try:
        logger.info("Running heuristic engine loop")
        asyncio.run(heuristic_process_loop(stop_event))
    except KeyboardInterrupt:
        logger.info("Heuristic engine interrupted")
    # pylint: disable=broad-exception-caught
    except Exception:
        logger.exception("Uncaught error in heuristic engine")
        raise
    finally:
        logger.info("Heuristic engine stopped")


if __name__ == "__main__":
    main()
