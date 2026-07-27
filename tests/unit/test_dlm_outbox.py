"""Tests for transactional outbox operations and relay delivery."""

import asyncio
import json
import os
from collections.abc import AsyncGenerator

import pytest
from aio_pika import ExchangeType, connect_robust
from aio_pika.exceptions import QueueEmpty
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ska_dlm.dlm_outbox import add_outbox_event


@pytest.fixture(name="engine")
async def engine_fixture() -> AsyncGenerator[AsyncEngine, None]:
    """Create an async engine for outbox database access."""
    database_url = os.getenv("DLM_OUTBOX_DATABASE_URL", "")
    if not database_url:
        pytest.skip("DLM_OUTBOX_DATABASE_URL is not configured")

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(name="outbox_session")
async def outbox_session_fixture(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create an async session bound to the configured outbox database."""
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)()
    try:
        yield async_session
    finally:
        await async_session.close()


@pytest.mark.asyncio
async def test_outbox_event_is_published_to_exchange(outbox_session: AsyncSession):
    """A published outbox event should reach a RabbitMQ subscriber with the same payload."""
    rabbitmq_url = os.getenv("DLM_OUTBOX_RABBITMQ_URL", "")
    if not rabbitmq_url:
        pytest.skip("DLM_OUTBOX_RABBITMQ_URL is not configured")

    exchange_name = os.getenv("DLM_OUTBOX_EXCHANGE", "dlm.outbox")
    event_type = "test-output-event"
    payload = {
        "id": "output-123",
        "status": "ready",
        "metadata": {"source": "pytest", "version": 1},
    }

    connection = await connect_robust(rabbitmq_url)
    try:
        async with connection.channel() as channel:
            exchange = await channel.declare_exchange(
                exchange_name, ExchangeType.TOPIC, durable=True
            )
            # Let RabbitMQ generate a unique queue name:
            queue = await channel.declare_queue(exclusive=True, auto_delete=True)
            await queue.bind(exchange, routing_key=event_type)

            outbox_event = await add_outbox_event(
                outbox_session,
                event_type=event_type,
                payload=payload,
                routing_key=event_type,
            )
            await outbox_session.commit()

            loop = asyncio.get_running_loop()
            deadline = loop.time() + 30
            while True:
                try:
                    message = await queue.get(fail=True)  # fail=True raises exception if empty
                    async with message.process():
                        received_payload = json.loads(message.body.decode("utf-8"))
                        assert received_payload == payload
                        assert message.headers["outbox_id"] == str(outbox_event.outbox_id)
                        assert message.headers["event_type"] == event_type
                        assert message.headers["created_at"] == outbox_event.created_at.isoformat()
                    break
                except QueueEmpty:
                    if loop.time() >= deadline:
                        pytest.fail("Outbox event was not published within 30 seconds")
                    await asyncio.sleep(1)  # Block manually before checking again
    finally:
        await connection.close()
