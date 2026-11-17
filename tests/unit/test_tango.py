"""Unit tests for the DLM Tango device."""
# inspiredby:
# https://gitlab.com/ska-telescope/sdp/ska-sdp-mock-receptor-devices/-/blob/main/tests/integration/test_mock_mccs_station_beam.py

import json
import logging
import time

import pytest
from tango import DevState
from tango.test_context import DeviceTestContext

from ska_dlm import __version__
from ska_dlm.dlm_tango.dlm_metrics_device import DLMMetrics, HealthState

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)  # temp


@pytest.fixture(name="tango_context")
def tango_context_fixture():
    """Create a Tango test device.

    Starts a temporary Tango device server for the duration of the test. It does not require
    Kubernetes, helm, a persistent Tango database or a separately deployed Tango container.
    """
    with DeviceTestContext(  # composed with a test database
        DLMMetrics,
        device_name="dlm/metrics/0",
        process=True,
    ) as context:
        yield context


def test_dlm_metrics(tango_context):
    """Verify that the DLM Tango device initialises, and exposes the DLM release version."""
    device = tango_context

    version_info = json.loads(tango_context.version)
    assert version_info == {"version": __version__}
    assert device.state() == DevState.ON


@pytest.mark.parametrize(
    "service_name",
    [
        "postgres",
        "postgrest",
        "rclone",
        # "heuristics", # TODO: Heuristics daemon runs as a background process w/o an HTTP endpoint
        "storage",
        "migration",
        "ingest",
        "request",
        "rabbitmq",
    ],
)
def test_service_health_state(tango_context, service_name):
    """Verify that the Tango device reports each service as healthy."""
    attribute_name = f"{service_name}HealthState"
    timeout = time.monotonic() + 10

    while time.monotonic() < timeout:
        health_state = getattr(tango_context, attribute_name)
        logger.debug("%s HealthState: %s", service_name, HealthState(health_state).name)

        if health_state == HealthState.OK:
            return
        time.sleep(0.5)

    assert getattr(tango_context, attribute_name) == HealthState.OK
