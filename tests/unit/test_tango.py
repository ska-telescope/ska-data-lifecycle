"""Unit tests for the DLM Tango device."""
# inspiredby:
# https://gitlab.com/ska-telescope/sdp/ska-sdp-mock-receptor-devices/-/blob/main/tests/integration/test_mock_mccs_station_beam.py

import json
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tango import DevState
from tango.test_context import DeviceTestContext

from ska_dlm import __version__
from ska_dlm.dlm_tango.dlm_metrics_device import DLMMetrics, HealthState, _count_active_migrations

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)  # temp


@pytest.fixture(name="dlm_metrics_device")
def dlm_metrics_device_fixture():
    """Create a Tango test device.

    Starts a temporary Tango device server for the duration of the test. It does not require
    Kubernetes, helm, a persistent Tango database or a separately deployed Tango container.
    """
    with DeviceTestContext(  # composed with a test database
        DLMMetrics,
        device_name="dlm/metrics/0",
        process=True,
    ) as dlm_metrics_device:  # returns a device proxy object to the tango device
        yield dlm_metrics_device


def test_dlm_metrics(dlm_metrics_device):
    """Verify that the DLM Tango device initialises, and exposes the DLM release version."""
    device = dlm_metrics_device

    version_info = json.loads(dlm_metrics_device.version)
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
def test_service_health_state(dlm_metrics_device, service_name):
    """Verify that the Tango device reports each service as healthy."""
    attribute_name = f"{service_name}HealthState"
    timeout = time.monotonic() + 10

    while time.monotonic() < timeout:
        health_state = getattr(dlm_metrics_device, attribute_name)
        logger.debug("%s HealthState: %s", service_name, HealthState(health_state).name)

        if health_state == HealthState.OK:
            return
        time.sleep(0.5)

    assert getattr(dlm_metrics_device, attribute_name) == HealthState.OK


@pytest.mark.asyncio
async def test_count_active_migrations():
    """Verify that the number of active migrations is returned from the database query."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = 3  # Simulate a query result containing 3 active migrations
    session.execute.return_value = result

    count = await _count_active_migrations(session)

    assert count == 3
    session.execute.assert_awaited_once()


# pylint: disable=protected-access
@pytest.mark.asyncio
async def test_migration_count_failure_does_not_affect_postgres_health():
    """Verify that a failed migration query does not mark PostgreSQL as unhealthy."""
    device = MagicMock()
    session = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "ska_dlm.dlm_tango.dlm_metrics_device._check_postgres_connection",
            new_callable=AsyncMock,  # mock _check_postgres_connection() to succeed
        ) as check_postgres,
        patch(
            "ska_dlm.dlm_tango.dlm_metrics_device._count_active_migrations",
            new_callable=AsyncMock,
            side_effect=Exception("Migration query failed"),  # mock migration query to fail
        ),
    ):
        await DLMMetrics._update_database_metrics(device, session_factory)

    check_postgres.assert_awaited_once_with(session)
    assert device._postgres_health_state == HealthState.OK
    assert str(device._migrations_in_progress) == "nan"
