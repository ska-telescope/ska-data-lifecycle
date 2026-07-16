"""Transactional outbox operations for DLM.

This module provides the lightweight database operations needed by the
transactional outbox relay. The helper functions are intentionally small
and designed to be called within an async SQLAlchemy transaction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import asc, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ska_dlm.common_types import OutboxStatus
from ska_dlm.dlm_db import Outbox


def _normalise_datetime(value: datetime | None) -> datetime | None:
    """Convert timezone-aware datetimes to the naive UTC form expected by the DB."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def add_outbox_event(
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    session: AsyncSession,
    event_type: str,
    payload: dict[str, Any],
    destination: str | None = None,
    routing_key: str | None = None,
    created_at: datetime | None = None,
) -> Outbox:
    """Insert a new outbox event in the database.

    Parameters
    ----------
    session : AsyncSession
        Async SQLAlchemy session used to persist the outbox event.
    event_type : str
        Logical name of the event. Also used as the default routing key.
    payload : dict[str, Any]
        JSON-serializable event body to deliver to RabbitMQ.
    destination : str | None
        Optional exchange name to publish to. If not set, the relay will use
        the configured default exchange.
    routing_key : str | None
        Optional routing key for RabbitMQ routing.
    created_at : datetime | None
        Optional creation timestamp override, useful for deterministic
        ordering in tests.

    Returns
    -------
    Outbox:
        The persisted outbox row instance.
    """
    values: dict[str, Any] = {
        "event_type": event_type,
        "payload": payload,
        "destination": destination,
        "routing_key": routing_key,
        "status": OutboxStatus.PENDING.value,
        "attempts": 0,
    }
    if created_at is not None:
        values["created_at"] = created_at

    outbox_event = Outbox(**values)
    session.add(outbox_event)
    await session.flush()
    return outbox_event


async def get_pending_outbox_events(session: AsyncSession, limit: int = 100) -> list[Outbox]:
    """Return pending outbox events ordered by creation time.

    The relay worker should call this function to fetch the next batch of
    messages ready for delivery.

    Parameters
    ----------
    session : AsyncSession
        Async SQLAlchemy session used for the query.
    limit : int
        Maximum number of pending events to return.

    Returns
    -------
    list[Outbox]:
        The list of pending outbox events.
    """
    stmt = (
        select(Outbox)
        .where(Outbox.status == OutboxStatus.PENDING.value)
        .order_by(asc(Outbox.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def mark_outbox_event_sent(
    session: AsyncSession, outbox_id: str, sent_at: datetime | None = None
) -> int:
    """Mark an outbox event as sent and increment the attempt counter.

    Parameters
    ----------
    session : AsyncSession
        Async SQLAlchemy session used for the update.
    outbox_id : str
        UUID string for the outbox event to update.
    sent_at : datetime
        Optional timestamp for when the event was delivered.

    Returns
    -------
    int:
        Number of rows updated.
    """
    timestamp = _normalise_datetime(sent_at or datetime.now(timezone.utc))
    stmt = (
        update(Outbox)
        .where(Outbox.outbox_id == outbox_id)
        .values(
            status=OutboxStatus.SENT.value,
            sent_at=timestamp,
            last_attempt=_normalise_datetime(datetime.now(timezone.utc)),
            attempts=Outbox.attempts + 1,
        )
    )
    result = await session.execute(stmt)
    return result.rowcount


async def mark_outbox_event_failed(
    session: AsyncSession, outbox_id: str, last_attempt: datetime | None = None
) -> int:
    """Mark an outbox event as failed and record the last attempt timestamp.

    Parameters
    ----------
    session : AsyncSession
        Async SQLAlchemy session used for the update.
    outbox_id : str
        UUID string for the outbox event to update.
    last_attempt : datetime
        Optional time when the publish attempt was made.

    Returns
    -------
    int:
        Number of rows updated.
    """
    stmt = (
        update(Outbox)
        .where(Outbox.outbox_id == outbox_id)
        .values(
            status=OutboxStatus.FAILED.value,
            last_attempt=_normalise_datetime(last_attempt or datetime.now(timezone.utc)),
            attempts=Outbox.attempts + 1,
        )
    )
    result = await session.execute(stmt)
    return result.rowcount


async def delete_old_sent_outbox_events(
    session: AsyncSession, cutoff: datetime | None = None
) -> int:
    """Delete sent outbox events older than the provided retention cutoff.

    Parameters
    ----------
    session : AsyncSession
        Async SQLAlchemy session used for the delete.
    cutoff : datetime
        Optional timestamp; events with a sent_at value older than or equal to
        this cutoff are removed. Defaults to one week ago from now.

    Returns
    -------
    int:
        Number of rows deleted.
    """
    threshold = _normalise_datetime(cutoff or datetime.now(timezone.utc) - timedelta(days=7))
    stmt = delete(Outbox).where(
        Outbox.status == OutboxStatus.SENT.value,
        Outbox.sent_at.isnot(None),
        Outbox.sent_at <= threshold,
    )
    result = await session.execute(stmt)
    return result.rowcount
