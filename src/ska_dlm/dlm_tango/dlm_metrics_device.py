"""Tango device for exposing DLM monitoring metrics."""

import json
import logging

from tango import DevState
from tango.server import Device, attribute, run

logger = logging.getLogger(__name__)


class DLMMetrics(Device):
    """Tango device exposing DLM service health information."""

    # pylint: disable=invalid-name

    @attribute(dtype=str)
    def version(self) -> str:
        """Return the DLM version and container image information."""
        return json.dumps(self._version)

    @attribute(dtype=bool)
    def rcloneHealthy(self) -> bool:
        """Whether the DLM Rclone service is healthy."""
        return self._rclone_healthy

    @attribute(dtype=bool)
    def postgrestHealthy(self) -> bool:
        """Whether the DLM PostgREST service is healthy."""
        return self._postgrest_healthy

    @attribute(dtype=bool)
    def ingestHealthy(self) -> bool:
        """Whether the DLM ingest service is healthy."""
        return self._ingest_healthy

    def init_device(self):
        """Initialise the Tango device."""
        super().init_device()

        # Mock values for initial development.
        self._version = {
            "version": "2.4.0",
            "image": "artefact.skao.int/ska-data-lifecycle:2.4.0",
        }
        self._rclone_healthy = True
        self._postgrest_healthy = True
        self._ingest_healthy = False

        self.set_state(DevState.ON)  # means the Tango device itself is operational.


def main():
    """Start the DLM Tango device server."""
    run(classes=(DLMMetrics,))


if __name__ == "__main__":
    main()
