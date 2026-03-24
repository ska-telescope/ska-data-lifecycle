"""SQLAlchemy ORM base and session helpers for DLM."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def get_engine(database_url: str, **kwargs):
    """Create a synchronous SQLAlchemy engine."""
    return create_engine(database_url, future=True, **kwargs)


# pylint: disable=invalid-name
def get_session(engine, **kwargs):
    """Create a synchronous session. Use from non-async code."""
    SessionLocal = sessionmaker(
        bind=engine, future=True, autoflush=False, autocommit=False, **kwargs
    )
    return SessionLocal()


def get_async_engine(database_url: str, **kwargs):
    """Create an async SQLAlchemy engine."""
    return create_async_engine(database_url, future=True, **kwargs)


# pylint: disable=invalid-name
def get_async_session(engine, **kwargs):
    """Create an async session. Use from async code."""
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        future=True,
        **kwargs,
    )
    return AsyncSessionLocal()
