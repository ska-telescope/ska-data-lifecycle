"""RabbitMQ relay daemon for the DLM transactional outbox.

This module implements a long-running loop that reads pending events from the
outbox table and publishes them to RabbitMQ. It also updates the outbox row
status to SENT or FAILED based on delivery results.
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timedelta, timezone

from aio_pika import DeliveryMode, Exchange, ExchangeType, Message, connect_robust
from sqlalchemy.ext.asyncio import AsyncSession

from ska_dlm.dlm_db import Outbox, create_async_sql_engine, create_async_sql_session
from ska_dlm.dlm_outbox.outbox import (
    delete_old_sent_outbox_events,
    get_pending_outbox_events,
    mark_outbox_event_failed,
    mark_outbox_event_sent,
)

logger = logging.getLogger(__name__)

OUTBOX_DATABASE_URL = os.getenv(
    "DLM_OUTBOX_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://ska_dlm_admin:password@dlm_db:5432/ska_dlm"),
)
RABBITMQ_URL = os.getenv(
    "DLM_OUTBOX_RABBITMQ_URL",
    os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/"),
)
OUTBOX_POLL_INTERVAL = int(os.getenv("DLM_OUTBOX_POLL_INTERVAL", "10"))
OUTBOX_BATCH_SIZE = int(os.getenv("DLM_OUTBOX_BATCH_SIZE", "50"))
DEFAULT_OUTBOX_EXCHANGE = os.getenv("DLM_OUTBOX_EXCHANGE", "dlm.outbox")


async def _publish_event(exchange: Exchange, event: Outbox) -> None:
    """Publish a single outbox event to RabbitMQ.

    The exchange is selected from the event's destination field or the default
    exchange. The routing key falls back to the event type if none is provided.

    Parameters
    ----------
    exchange : Exchange
        RabbitMQ exchange to publish the event to.
    event : Outbox
        Outbox event to publish.
    """
    routing_key = event.routing_key or event.event_type

    headers = {
        "outbox_id": str(event.outbox_id),
        "event_type": event.event_type,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }

    message = Message(
        body=json.dumps(event.payload).encode("utf-8"),
        content_type="application/json",
        headers=headers,
        delivery_mode=DeliveryMode.PERSISTENT,
    )

    await exchange.publish(message, routing_key=routing_key)


async def _process_pending_events(exchange: Exchange, session: AsyncSession) -> int:
    """Fetch pending outbox events and attempt to publish them.

    Returns the number of events successfully published.

    Parameters
    ----------
    exchange : Exchange
        RabbitMQ exchange to publish the event to.
    session : AsyncSession
        Async SQLAlchemy session used to persist the outbox event.

    Returns
    -------
    int
        The number of events successfully published.
    """
    events = await get_pending_outbox_events(session, limit=OUTBOX_BATCH_SIZE)
    if not events:
        return 0

    processed = 0
    for event in events:
        try:
            await _publish_event(exchange, event)
            await mark_outbox_event_sent(
                session,
                str(event.outbox_id),
                sent_at=datetime.now(timezone.utc),
            )
            await session.commit()
            processed += 1
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to publish outbox event %s", event.outbox_id)
            await mark_outbox_event_failed(
                session,
                str(event.outbox_id),
                last_attempt=datetime.now(timezone.utc),
            )
            await session.commit()

    deleted = await delete_old_sent_outbox_events(
        session,
        cutoff=datetime.now(timezone.utc) - timedelta(days=7),
    )
    if deleted:
        await session.commit()
        logger.info("Deleted %s old sent outbox event(s)", deleted)
    return processed


async def outbox_relay_loop(stop_event: asyncio.Event) -> None:
    """Run the outbox relay until a stop event is triggered.

    The loop polls the outbox table at a fixed interval, publishes pending
    messages to RabbitMQ, and updates their delivery state.

    Parameters
    ----------
    stop_event : asyncio.Event
        An asyncio.Event that, when set, will stop the relay loop.

    """
    if RABBITMQ_URL is None:
        raise RuntimeError("RABBITMQ URL is required for the outbox relay")

    engine = create_async_sql_engine(OUTBOX_DATABASE_URL)
    connection = await connect_robust(RABBITMQ_URL)

    async with connection.channel() as channel:
        exchange = await channel.declare_exchange(
            DEFAULT_OUTBOX_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )

        loop_counter = 0
        while not stop_event.is_set():
            start = datetime.now(timezone.utc)
            loop_counter += 1
            logger.debug("Outbox relay loop %s starting at %s", loop_counter, start.isoformat())
            try:
                async_session = create_async_sql_session(engine)
                async with async_session as session:
                    processed = await _process_pending_events(exchange, session)

                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                sleep_time = max(0, OUTBOX_POLL_INTERVAL - elapsed)
                if processed > 0:
                    logger.info("Published %s outbox event(s)", processed)
                await asyncio.wait_for(stop_event.wait(), timeout=sleep_time)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("Outbox relay cancelled")
                break
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Outbox relay iteration failed; continuing")

    try:
        await engine.dispose()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Failed to dispose outbox DB engine")


def _configure_signals(stop_event: asyncio.Event):
    """Bind SIGINT and SIGTERM to stop the relay cleanly."""

    def _handler(*_):
        logger.info("Signal received: stopping outbox relay")
        stop_event.set()

    signal.signal(signal.SIGINT, lambda sig, frame: _handler())
    signal.signal(signal.SIGTERM, lambda sig, frame: _handler())


def main() -> None:
    """Entrypoint for the DLM outbox relay process."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Starting DLM outbox relay")

    stop_event = asyncio.Event()
    _configure_signals(stop_event)

    try:
        logger.info("Running DLM outbox relay loop")
        asyncio.run(outbox_relay_loop(stop_event))
    except KeyboardInterrupt:
        logger.info("Outbox relay interrupted")
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Uncaught error in outbox relay")
    finally:
        logger.info("Outbox relay stopped")


if __name__ == "__main__":
    main()
