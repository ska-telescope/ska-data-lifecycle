"""Tango device for exposing DLM monitoring metrics."""

import json
import logging
import os

from tango import DevState
from tango.server import Device, attribute, run

from ska_dlm import __version__
from ska_dlm.dlm_tango.attributes import HealthState

logger = logging.getLogger(__name__)


class DLMMetrics(Device):
    """Tango device exposing DLM service health information."""

    # pylint: disable=invalid-name, too-many-instance-attributes

    @attribute(dtype=str)
    def version(self) -> str:
        """Return the DLM version."""
        return json.dumps({"version": __version__})

    @attribute(dtype=str)
    def image(self) -> str:
        """Return the image reference configured by Helm."""
        return json.dumps({"image": os.getenv("DLM_IMAGE", "unknown")})  # Helm image reference

    @attribute(dtype=HealthState)
    def rcloneHealthy(self) -> HealthState:
        """Return the health of the DLM rclone service."""
        return self._rclone_healthy

    @attribute(dtype=HealthState)
    def postgresHealthy(self) -> HealthState:
        """Whether the PostgreSQL database is reachable."""
        return self._postgres_healthy

    @attribute(dtype=HealthState)
    def postgrestHealthy(self) -> HealthState:
        """Return the health of the DLM PostgREST service."""
        return self._postgrest_healthy

    @attribute(dtype=HealthState)
    def etcdHealthy(self) -> HealthState:
        """Return the health of the etcd service."""
        return self._etcd_healthy

    @attribute(dtype=HealthState)
    def heuristicsHealthy(self) -> HealthState:
        """Return the health of the DLM heuristics service."""
        return self._heuristics_healthy

    @attribute(dtype=HealthState)
    def storageHealthy(self) -> HealthState:
        """Return the health of the DLM storage service."""
        return self._storage_healthy

    @attribute(dtype=HealthState)
    def migrationHealthy(self) -> HealthState:
        """Return the health of the DLM migration service."""
        return self._migration_healthy

    @attribute(dtype=HealthState)
    def ingestHealthy(self) -> HealthState:
        """Return the health of the DLM ingest service."""
        return self._ingest_healthy

    @attribute(dtype=HealthState)
    def requestHealthy(self) -> HealthState:
        """Return the health of the DLM request service."""
        return self._request_healthy

    @attribute(dtype=HealthState)
    def rabbitmqHealthy(self) -> HealthState:
        """Return the health of the DLM RabbitMQ service."""
        return self._rabbitmq_healthy

    @attribute(dtype=HealthState)
    def outboxHealthy(self) -> HealthState:
        """Return the health of the DLM outbox service."""
        return self._outbox_healthy

    @attribute(dtype=HealthState)
    def dlmHealthy(self) -> HealthState:
        """Return the overall health of the DLM subsystem."""
        return self._dlm_healthy

    @attribute(dtype=(str,))
    def storageEndPoints(self) -> list[str]:
        """Return a list of storage endpoints registered in the database."""
        return self._storage_endpoints

    @attribute(dtype=(float,))
    def storageUsedPct(self) -> list[float]:
        """Return the percentage of storage capacity used for each storage endpoint."""
        return self._storage_used_pct

    @attribute(dtype=int)
    def migrationsInProgress(self) -> int:
        """Return the number of migrations currently in progress."""
        return self._migrations_in_progress

    def init_device(self):
        """Initialise the Tango device."""
        super().init_device()

        # Placeholder values, TODO: DMAN-324
        self._rclone_healthy = HealthState.UNKNOWN
        self._postgres_healthy = HealthState.UNKNOWN
        self._postgrest_healthy = HealthState.UNKNOWN
        self._etcd_healthy = HealthState.UNKNOWN
        self._heuristics_healthy = HealthState.UNKNOWN
        self._storage_healthy = HealthState.UNKNOWN
        self._migration_healthy = HealthState.UNKNOWN
        self._ingest_healthy = HealthState.UNKNOWN
        self._request_healthy = HealthState.UNKNOWN
        self._rabbitmq_healthy = HealthState.UNKNOWN
        self._outbox_healthy = HealthState.UNKNOWN
        self._dlm_healthy = HealthState.UNKNOWN
        self._storage_endpoints = ["dlm-archive", "local"]
        self._storage_used_pct = [0.0, 0.0]
        self._migrations_in_progress = 0

        self.set_state(DevState.ON)  # means the Tango device itself is operational.


def main():
    """Start the DLM Tango device server."""
    run(classes=(DLMMetrics,))


if __name__ == "__main__":
    main()
