# pylint: disable=R0914
"""Heuristic engine daemon using SQLAlchemy ORM (asyncio)."""

import asyncio
import logging
import math
import os
import signal
from datetime import datetime, timezone

from ska_dlm.dlm_db import create_async_sql_engine, create_async_sql_session
from ska_dlm.dlm_heuristics.heuristics import (
    EnforceStorageUsageHeuristic,
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


async def heuristic_process_loop(stop_event: asyncio.Event):
    """Run heuristic iteration until stop event is set."""
    async with create_async_sql_engine(HEURISTIC_DATABASE_URL) as engine:
        async_session = create_async_sql_session(engine)
        loop_counter = 0
        total_sleep_time = 0
        loop_start = datetime.now(timezone.utc)
        while not stop_event.is_set():
            start = datetime.now(timezone.utc)

            loop_counter += 1
            logger.debug("Heuristic engine loop %s tick at %s", loop_counter, start.isoformat())
            try:
                # we are packing each called heuristics in it's own session
                async with async_session as session:
                    uid_expiry_heuristics = UidExpiryHeuristic(session)
                    uid_expiry_result = await uid_expiry_heuristics.execute()
                    await session.commit()
                logger.info("UID expiry heuristics returned: %s", uid_expiry_result.message)
                if not uid_expiry_result.success:
                    logger.debug("UID expiry data: %s", uid_expiry_result.data)

                async with async_session as session:
                    oid_expiry_heuristics = OidExpiryHeuristic(session)
                    oid_expiry_result = await oid_expiry_heuristics.execute()
                    await session.commit()
                logger.info("OID expiry heuristics returned: %s", oid_expiry_result.message)
                if not oid_expiry_result.success:
                    logger.debug("OID expiry data: %s", oid_expiry_result.data)

                async with async_session as session:
                    storage_usage_heuristics = UpdateStorageUsageHeuristic(session)
                    storage_usage_result = await storage_usage_heuristics.execute()
                    await session.commit()
                logger.info("Storage usage heuristics returned: %s", storage_usage_result.message)
                if not storage_usage_result.success:
                    logger.debug("Storage usage result data: %s", storage_usage_result.data)

                async with async_session as session:
                    enforce_storage_usage_heuristics = EnforceStorageUsageHeuristic(session)
                    enforce_storage_usage_result = await enforce_storage_usage_heuristics.execute()
                    await session.commit()
                logger.info(
                    "Enforce storage usage heuristics returned: status: %s; message: %s",
                    enforce_storage_usage_result.success, enforce_storage_usage_result.message,
                )
                logger.info(">>> Temporarily output of all info: %s", enforce_storage_usage_result.data)
                if not enforce_storage_usage_result.success:
                    logger.debug(
                        "Enforce storage usage data: %s", enforce_storage_usage_result.data
                    )
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                sleep_time = max(0, HEURISTIC_POLL_INTERVAL - elapsed)
                total_sleep_time += sleep_time
                await asyncio.wait_for(stop_event.wait(), timeout=sleep_time)
            except asyncio.exceptions.TimeoutError:
                if loop_counter % 10 == 0:
                    average_sleep_time = total_sleep_time / loop_counter
                    logger.info(
                        "Heuristic engine loop number: %s; average sleep time/loop: %5.2f s",
                        loop_counter,
                        average_sleep_time,
                    )

                    loop_time = (
                        datetime.now(timezone.utc) - loop_start
                    ).total_seconds() / loop_counter
                    if average_sleep_time < HEURISTIC_POLL_INTERVAL / 10:
                        suggested_interval = (
                            math.ceil(loop_time / HEURISTIC_POLL_INTERVAL)
                            * HEURISTIC_POLL_INTERVAL
                        )
                        if suggested_interval > HEURISTIC_POLL_INTERVAL:
                            logger.info(
                                "Suggested value for HEURISTIC_POLL_INTERVAL: %5.0f",
                                suggested_interval,
                            )
                continue
            except asyncio.exceptions.CancelledError:
                logger.info("Heuristic loop cancelled")
                break
            # pylint: disable=broad-exception-caught
            except Exception:
                logger.exception("Heuristic engine iteration %d failed; continuing", loop_counter)


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
    finally:
        logger.info("Heuristic engine stopped")


if __name__ == "__main__":
    main()
