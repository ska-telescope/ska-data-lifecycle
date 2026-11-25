"""Tango device for exposing DLM monitoring metrics."""

import asyncio
import json
import logging
import os
from threading import Event, Thread, current_thread
from typing import cast

import requests
from ska_control_model import HealthState
from sqlalchemy import func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tango import ArgType, DevState, EnsureOmniThread
from tango.server import Device, attribute, device_property

from ska_dlm import __version__
from ska_dlm.dlm_db import Migration, Storage

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class DLMMetrics(Device):
    """Tango device exposing DLM service health information."""

    # pylint: disable=invalid-name, too-many-instance-attributes, attribute-defined-outside-init

    @attribute
    def version(self) -> str:
        """Return the DLM version."""
        return json.dumps({"version": __version__})  # TODO: this is probably an oversimplification

    @attribute
    def image(self) -> str:
        """Return the image reference configured by Helm."""
        return json.dumps({"image": os.getenv("DLM_IMAGE", "unknown")})  # Helm image reference

    @attribute
    def rcloneHealthState(self) -> HealthState:
        """Return the health of the DLM rclone service."""
        return self._rclone_health_state

    @attribute
    def postgresHealthState(self) -> HealthState:
        """Whether the PostgreSQL database is reachable."""
        return self._postgres_health_state

    @attribute
    def postgrestHealthState(self) -> HealthState:
        """Return the health of the DLM PostgREST service."""
        return self._postgrest_health_state

    @attribute
    def heuristicsHealthState(self) -> HealthState:  # TODO (no HTTP endpoint)
        """Return the health of the DLM heuristics service.

        # TODO: Implement a health check for the heuristics daemon.
        # It has no HTTP endpoint. Could add a tiny HTTP server to the existing heuristics
        # daemon, running alongside heuristic_process_loop() ?
        """
        return self._heuristics_health_state

    @attribute
    def storageHealthState(self) -> HealthState:
        """Return the health of the DLM storage service."""
        return self._storage_health_state

    @attribute
    def migrationHealthState(self) -> HealthState:
        """Return the health of the DLM migration service.

        TODO: in addition, if rabbitmq or outbox is down, migration is DEGRADED.
        """
        return self._migration_health_state

    @attribute
    def ingestHealthState(self) -> HealthState:
        """Return the health of the DLM ingest service."""
        return self._ingest_health_state

    @attribute
    def requestHealthState(self) -> HealthState:
        """Return the health of the DLM request service."""
        return self._request_health_state

    @attribute
    def rabbitmqHealthState(self) -> HealthState:
        """Return the health of the DLM RabbitMQ service."""
        return self._rabbitmq_health_state

    @attribute
    def outboxHealthState(self) -> HealthState:  # TODO (no HTTP endpoint)
        """Return the health of the DLM outbox service."""
        return self._outbox_health_state

    @attribute  # TODO: if any of the services are down, dlmHealthState is DEGRADED.
    def dlmHealthState(self) -> HealthState:
        """Return the overall health of the DLM subsystem."""
        return self._dlm_health_state

    @attribute(max_dim_x=100)
    def storageEndPoints(self) -> list[str]:
        """Return a list of storage endpoints registered in the database."""
        return self._storage_endpoints

    @attribute(max_dim_x=100)  # TODO (storageUsedPct is not yet implemented)
    def storageUsedPct(self) -> list[float]:
        """Return the percentage of storage capacity used for each storage endpoint."""
        return self._storage_used_pct

    @attribute
    def migrationsInProgress(self) -> float:
        """Return the number of migrations currently in progress."""
        return self._migrations_in_progress

    polling_interval = device_property(dtype=ArgType.DevULong, default_value=10000)
    """Polling interval in milliseconds. Default 10000."""

    def init_device(self):
        """Initialise the Tango device. WIP."""
        super().init_device()
        logger.debug("Connecting to Tango database at %s...", os.getenv("TANGO_HOST"))

        self._stop_event = Event()  # initially unset (equivalent to False)
        self._health_thread: Thread | None = None  # initialise background monitoring thread

        # initialise all attributes:
        self._postgres_health_state = HealthState.UNKNOWN
        self._postgrest_health_state = HealthState.UNKNOWN
        self._rclone_health_state = HealthState.UNKNOWN
        self._heuristics_health_state = HealthState.UNKNOWN
        self._storage_health_state = HealthState.UNKNOWN
        self._migration_health_state = HealthState.UNKNOWN
        self._ingest_health_state = HealthState.UNKNOWN
        self._request_health_state = HealthState.UNKNOWN
        self._rabbitmq_health_state = HealthState.UNKNOWN
        self._outbox_health_state = HealthState.UNKNOWN
        self._dlm_health_state = HealthState.UNKNOWN
        self._storage_endpoints = []
        self._storage_used_pct = [float("nan"), float("nan")]
        self._migrations_in_progress = float("nan")

        # Run periodic health checks in a background thread without blocking the Tango device:
        self._health_thread = Thread(
            target=self._health_update_loop,
            daemon=True,
        )
        self._health_thread.start()
        self.set_state(DevState.ON)  # Tango device is operational

    def _update_health(self, service_name: str, check, *args):
        """Run a health check, update the corresponding state, and log any failures."""
        try:
            check(*args)  # calls the function passed in as check, using any args passed in
            state = HealthState.OK
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("%s health check failed.", service_name)
            state = HealthState.FAILED

        setattr(self, f"_{service_name.lower()}_health_state", state)

    def _health_update_loop(self):
        """Run the asynchronous monitoring loop in a dedicated background thread.

        Create a single asyncio event loop for the lifetime of the thread, allowing the async
        database engine to be reused safely.
        """
        with EnsureOmniThread():
            asyncio.run(self._async_health_update_loop())

    async def _async_health_update_loop(self):
        """Periodically update DLM service health and database metrics.

        Create the asynchronous SQLAlchemy engine and session factory once, outside the polling
        loop, rather than establishing a new engine on every iteration.
        Reuse them for all database checks.
        Run the existing synchronous HTTP health checks in the same monitoring thread.
        Dispose of the database engine when monitoring stops.

        Service URLs are supplied through environment variables, with defaults corresponding to the
        DLM service names.
        """
        url = URL.create(
            "postgresql+asyncpg",
            username=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
            host=os.environ["PGHOST"],
            port=int(os.getenv("PGPORT", "5432")),
            database=os.environ["PGDATABASE"],
        )

        engine = create_async_engine(url, connect_args={"timeout": 5})
        async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            while not self._stop_event.is_set():
                await self._update_database_metrics(async_session_factory)

                self._update_health(
                    "postgrest",
                    _check_http_health,
                    os.getenv("DLM_POSTGREST_URL", "http://ska-dlm-postgrest:80").rstrip("/"),
                )
                self._update_health(
                    "rclone",
                    _check_rclone_health,
                    os.getenv("DLM_RCLONE_URL", "http://ska-dlm-rclone:80").rstrip("/"),
                )
                self._update_health(
                    "storage",
                    _check_http_health,
                    os.getenv("DLM_STORAGE_URL", "http://ska-dlm-storage:80").rstrip("/")
                    + "/openapi.json",
                )
                self._update_health(
                    "migration",
                    _check_http_health,
                    os.getenv("DLM_MIGRATION_URL", "http://ska-dlm-migration:80").rstrip("/")
                    + "/openapi.json",
                )
                self._update_health(
                    "ingest",
                    _check_http_health,
                    os.getenv("DLM_INGEST_URL", "http://ska-dlm-ingest:80").rstrip("/")
                    + "/openapi.json",
                )
                self._update_health(
                    "request",
                    _check_http_health,
                    os.getenv("DLM_REQUEST_URL", "http://ska-dlm-request:80").rstrip("/")
                    + "/openapi.json",
                )
                self._update_health(
                    "rabbitmq",  # Will this fail if the management API requires authentication?
                    _check_http_health,
                    os.getenv("DLM_RABBITMQ_URL", "http://ska-dlm-rabbitmq:15672/").rstrip("/"),
                )

                # Logging the attributes. Can remove later.
                logger.info("PostgreSQL HealthState: %s", self._postgres_health_state.name)
                logger.info("PostgREST HealthState: %s", self._postgrest_health_state.name)
                logger.info("rclone HealthState: %s", self._rclone_health_state.name)
                logger.info("heuristics HealthState: %s", self._heuristics_health_state.name)
                logger.info("storage HealthState: %s", self._storage_health_state.name)
                logger.info("migration HealthState: %s", self._migration_health_state.name)
                logger.info("ingest HealthState: %s", self._ingest_health_state.name)
                logger.info("request HealthState: %s", self._request_health_state.name)
                logger.info("rabbitmq HealthState: %s", self._rabbitmq_health_state.name)
                logger.info("No. of migrations in progress: %s", self._migrations_in_progress)
                logger.info("All storage endpoints: %s\n", self._storage_endpoints)

                self._stop_event.wait(cast(int, self.polling_interval) / 1000)

        finally:
            await engine.dispose()

    async def _update_database_metrics(self, async_session_factory):
        """Update PostgreSQL health and the number of active migrations.

        Use a single session for both queries.
        If PostgreSQL is unreachable, mark its health as FAILED and the migration count as NaN.
        If only the migration count fails, leave PostgreSQL health as OK.
        """
        async with async_session_factory() as session:
            try:
                await _check_postgres_connection(session)

            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("PostgreSQL health check failed.")
                self._postgres_health_state = HealthState.FAILED
                # reset attributes:
                self._migrations_in_progress = float("nan")
                self._storage_endpoints = []

            else:
                self._postgres_health_state = HealthState.OK

                try:
                    self._migrations_in_progress = float(await _count_active_migrations(session))

                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to count active migrations.")
                    self._migrations_in_progress = float("nan")

                try:
                    self._storage_endpoints = await _read_storage_endpoints(session)

                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to read storage endpoints.")
                    self._storage_endpoints = []

    def delete_device(self):
        """Stop background tasks when the Tango device shuts down."""
        self._stop_event.set()  # set to True – the next time the loop checks is_set(), it exits.

        if self._health_thread is not None:
            if self._health_thread is not current_thread():
                self._health_thread.join(timeout=10)

        super().delete_device()


def _check_http_health(url: str) -> None:
    """Check whether an HTTP service is responding successfully (synchronous HTTP request)."""
    response = requests.get(url, timeout=5)
    response.raise_for_status()


def _check_rclone_health(url: str) -> None:
    """Check whether Rclone's Remote Control API is responding."""
    response = requests.post(
        f"{url.rstrip('/')}/rc/noop",
        json={"my_key": "my_value"},
        timeout=5,
        verify=False,
    )
    response.raise_for_status()


async def _check_postgres_connection(session: AsyncSession):
    """Verify PostgreSQL connectivity using an existing asynchronous session.

    Execute a simple query without modifying database records.
    Connection and session management are handled by the caller.
    """
    await session.execute(text("SELECT 1"))


async def _count_active_migrations(session: AsyncSession) -> int:
    """Query PostgreSQL and returns the number of active migrations.

    Receives a session and executes the query.
    """
    stmt = select(func.count(Migration.migration_id)).where(  # pylint: disable=not-callable
        Migration.complete.is_(False)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def _read_storage_endpoints(session: AsyncSession) -> list[str]:
    """Query PostgreSQL and returns the names of all storage endpoints.

    Receives a session and executes the query.
    """
    stmt = select(Storage.storage_name).order_by(Storage.storage_name)
    result = await session.execute(stmt)
    return list(result.scalars().all())
