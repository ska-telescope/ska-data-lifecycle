"""Heuristic engine daemon using SQLAlchemy ORM (asyncio)."""

import asyncio
import logging
import os
import signal
from datetime import datetime, timezone

from sqlalchemy import text

from ska_dlm.dlm_db import get_async_engine, get_async_session
from ska_dlm.dlm_db.orm import Base

logger = logging.getLogger(__name__)

HEURISTIC_DATABASE_URL = os.getenv(
    "DLM_HEURISTIC_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://ska_dlm_admin:password@dlm_db:5432/ska_dlm"),
)
HEURISTIC_POLL_INTERVAL = int(os.getenv("DLM_HEURISTIC_POLL_INTERVAL", "10"))


async def heuristic_process_loop(stop_event: asyncio.Event):
    """Run heuristic iteration until stop event is set."""
    engine = get_async_engine(HEURISTIC_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = get_async_session(engine)

    while not stop_event.is_set():
        start = datetime.now(timezone.utc)
        logger.debug("Heuristic engine tick at %s", start.isoformat())

        try:
            async with async_session as session:
                # Example query to keep the session alive; replace with real work
                await session.execute(text("SELECT 1"))
                await session.commit()

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            sleep_time = max(0, HEURISTIC_POLL_INTERVAL - elapsed)
            logger.debug("Sleeping %s seconds", sleep_time)
            await asyncio.wait([stop_event.wait()], timeout=sleep_time)

        except asyncio.CancelledError:
            logger.info("Heuristic loop cancelled")
            break
        # pylint: disable=broad-exception-caught
        except Exception:
            logger.exception("Heuristic engine iteration failed; continuing")

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
