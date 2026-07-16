"""SQLAlchemy ORM base and session helpers for DLM."""

import contextlib
import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def create_sql_engine(database_url: str, **kwargs):
    """Create a synchronous SQLAlchemy engine."""
    return create_engine(database_url, future=True, **kwargs)


def create_sql_session(engine, **kwargs):
    """Create a synchronous session. Use from non-async code."""
    return sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False, **kwargs)()


@contextlib.asynccontextmanager
async def create_async_sql_engine(database_url: str, **kwargs):
    """Create an async SQLAlchemy engine."""
    engine = create_async_engine(database_url, future=True, **kwargs)
    yield engine
    try:
        await engine.dispose()
    except Exception:  # pylint: disable=broad-exception-caught
        logging.exception("Failed to dispose sql engine to %s", database_url)


def create_async_sql_session(engine, **kwargs):
    """Create an async session. Use from async code."""
    return sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        future=True,
        **kwargs,
    )()
