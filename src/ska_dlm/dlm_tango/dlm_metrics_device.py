"""Tango device for exposing DLM monitoring metrics."""

import asyncio
import json
import logging
import os

from ska_control_model import HealthState
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from tango import DevState
from tango.server import Device, attribute, run

from ska_dlm import __version__

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class DLMMetrics(Device):
    """Tango device exposing DLM service health information."""

    # pylint: disable=invalid-name, too-many-instance-attributes

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
    def etcdHealthState(self) -> HealthState:
        """Return the health of the etcd service."""
        return self._etcd_health_state

    @attribute
    def heuristicsHealthState(self) -> HealthState:
        """Return the health of the DLM heuristics service."""
        return self._heuristics_health_state

    @attribute
    def storageHealthState(self) -> HealthState:
        """Return the health of the DLM storage service."""
        return self._storage_health_state

    @attribute
    def migrationHealthState(self) -> HealthState:
        """Return the health of the DLM migration service."""
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
    def outboxHealthState(self) -> HealthState:
        """Return the health of the DLM outbox service."""
        return self._outbox_health_state

    @attribute
    def dlmHealthState(self) -> HealthState:
        """Return the overall health of the DLM subsystem."""
        return self._dlm_health_state

    @attribute(max_dim_x=100)
    def storageEndPoints(self) -> list[str]:
        """Return a list of storage endpoints registered in the database."""
        return self._storage_endpoints

    @attribute(max_dim_x=100)
    def storageUsedPct(self) -> list[float]:
        """Return the percentage of storage capacity used for each storage endpoint."""
        return self._storage_used_pct

    @attribute
    def migrationsInProgress(self) -> float:
        """Return the number of migrations currently in progress."""
        return self._migrations_in_progress

    def init_device(self):
        """Initialise the Tango device."""
        super().init_device()

        # Placeholder values, TODO: DMAN-324
        self._rclone_health_state = HealthState.UNKNOWN
        self._postgres_health_state = HealthState.UNKNOWN
        self._postgrest_health_state = HealthState.UNKNOWN
        self._etcd_health_state = HealthState.UNKNOWN
        self._heuristics_health_state = HealthState.UNKNOWN
        self._storage_health_state = HealthState.UNKNOWN
        self._migration_health_state = HealthState.UNKNOWN
        self._ingest_health_state = HealthState.UNKNOWN
        self._request_health_state = HealthState.UNKNOWN
        self._rabbitmq_health_state = HealthState.UNKNOWN
        self._outbox_health_state = HealthState.UNKNOWN
        self._dlm_health_state = HealthState.UNKNOWN
        self._storage_endpoints = ["dlm-archive", "local"]
        self._storage_used_pct = [float("nan"), float("nan")]
        self._migrations_in_progress = float("nan")  # Use AttrQuality.ATTR_INVALID instead?

        self.set_state(DevState.ON)  # means the Tango device itself is operational.

        print("DLM Tango device initialised successfully!", flush=True)
        asyncio.run(_check_postgres_connection())


async def _check_postgres_connection():
    """Verify that the PostgreSQL connection works."""
    url = URL.create(
        "postgresql+asyncpg",
        username=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        host=os.environ["PGHOST"],
        port=int(os.getenv("PGPORT", "5432")),
        database=os.environ["PGDATABASE"],
    )

    engine = create_async_engine(url, connect_args={"timeout": 5})

    try:
        async with engine.connect():
            logger.info("Successfully connected to PostgreSQL!")
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Failed to connect to PostgreSQL")
    finally:
        await engine.dispose()


def main():
    """Start the DLM Tango device server."""
    asyncio.run(_check_postgres_connection())
    run(classes=(DLMMetrics,))


if __name__ == "__main__":
    main()
