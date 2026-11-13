"""SQLAlchemy ORM base and session helpers for DLM."""

import contextlib
import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def get_async_database_url(service_url_env: str) -> str:
    """Get an async SQLAlchemy URL from service or PostgreSQL environment variables."""
    database_url = os.getenv(service_url_env) or os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    required_env = ("PGUSER", "PGPASSWORD", "PGHOST", "PGDATABASE")
    missing_env = [name for name in required_env if not os.getenv(name)]
    if missing_env:
        raise RuntimeError(
            f"Configure {service_url_env}, DATABASE_URL, or all of " f"{', '.join(required_env)}"
        )

    return URL.create(
        "postgresql+asyncpg",
        username=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        host=os.environ["PGHOST"],
        port=int(os.getenv("PGPORT") or "5432"),
        database=os.environ["PGDATABASE"],
    ).render_as_string(hide_password=False)


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
