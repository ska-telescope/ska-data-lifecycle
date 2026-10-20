"""Unit tests for the DLM Tango device."""
# inspiredby:
# https://gitlab.com/ska-telescope/sdp/ska-sdp-mock-receptor-devices/-/blob/main/tests/integration/test_mock_mccs_station_beam.py

import json

import pytest
from tango import DevState
from tango.test_context import DeviceTestContext

from ska_dlm.dlm_tango.dlm_metrics_device import DlmMetrics


@pytest.fixture(name="tango_context")
def tango_context_fixture():
    """Create a Tango test device."""
    with DeviceTestContext(  # composed with a test database
        DlmMetrics,
        device_name="dlm/metrics/0",
        process=False,
    ) as context:
        yield context


def test_dlm_metrics(tango_context):
    """Test that the DLM Tango device exposes service health attributes."""
    device = tango_context

    version_info = json.loads(tango_context.version)

    assert version_info == {
        "version": "2.4.0",
        "image": "registry.gitlab.com/ska-telescope/ska-data-lifecycle/ska-data-lifecycle",
    }
    assert device.state() == DevState.ON
    assert device.rcloneHealthy is True
    assert device.postgrestHealthy is True
    assert device.ingestHealthy is False
