"""Heuristic engine daemon using SQLAlchemy ORM (asyncio)."""

import asyncio
import logging
import math
import os
import signal
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import text

from ska_dlm.dlm_db import create_async_sql_engine, create_async_sql_session
from ska_dlm.dlm_db.orm import Base
from ska_dlm.dlm_heuristics.heuristics import UidExpiryHeuristic

logger = logging.getLogger(__name__)

HEURISTIC_DATABASE_URL = os.getenv(
    "DLM_HEURISTIC_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://ska_dlm_admin:password@dlm_db:5432/ska_dlm"),
)
HEURISTIC_POLL_INTERVAL = int(os.getenv("DLM_HEURISTIC_POLL_INTERVAL", "10"))


async def heuristic_process_loop(stop_event: asyncio.Event):
    """Run heuristic iteration until stop event is set."""
    engine = create_async_sql_engine(HEURISTIC_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
                uidExpiryHeuristic = UidExpiryHeuristic(session)
                await uidExpiryHeuristic.execute()
                await session.commit()

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
                if average_sleep_time < HEURISTIC_POLL_INTERVAL/10:
                    suggested_interval = (
                        math.ceil(loop_time / HEURISTIC_POLL_INTERVAL) * HEURISTIC_POLL_INTERVAL
                    )
                    if suggested_interval > HEURISTIC_POLL_INTERVAL:
                        logger.info(
                            "Suggested value for HEURISTIC_POLL_INTERVAL: %5.0f", suggested_interval
                        )
            continue
        except asyncio.exceptions.CancelledError:
            logger.info("Heuristic loop cancelled")
            break
        # pylint: disable=broad-exception-caught
        except Exception:
            logger.exception("Heuristic engine iteration %d failed; continuing", loop_counter)

    try:
        await engine.dispose()
    # pylint: disable=broad-exception-caught
    except Exception:
        logger.exception("Failed to dispose heuristic DB engine")


def _configure_signals(stop_event: asyncio.Event):
    def _handler(*_):
        logger.info("Signal received: stopping heuristic engine")
        stop_event.set()

    signal.signal(signal.SIGINT, lambda sig, frame: _handler())
    signal.signal(signal.SIGTERM, lambda sig, frame: _handler())


def main() -> None:
    """Entrypoint for the heuristic engine process."""
    logger.info("Starting DLM heuristic engine")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
