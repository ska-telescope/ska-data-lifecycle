"""Unit tests for dlm_ingest."""

import logging
import uuid
from pathlib import Path

import pytest
import requests
from pytest_mock import MockerFixture
from requests_mock import Mocker

from ska_dlm import CONFIG, dlm_ingest


@pytest.fixture(name="mock_ingest_requests_storage", autouse=True)
def fixture_mock_ingest_requests_storage(mocker: MockerFixture):
    """Fixture to mock all storage related calls used in dlm_ingest_requests."""
    mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.query_storage",
        return_value=[
            {
                "storage_id": uuid.uuid4(),
                "storage_phase_level": "some-phase-level",
                "root_directory": "/root/",
            }
        ],
    )
    mocker.patch("ska_dlm.dlm_storage.dlm_storage_requests.rclone_access", return_value=True)
    mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.check_storage_access", return_value=True)


@pytest.fixture(name="mock_init_data_item")
def fixture_mock_init_data_item(mocker: MockerFixture):
    """Fixture for mocking init_data_item."""
    return mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.init_data_item", return_value="test-uid"
    )


@pytest.fixture(name="mock_update_data_item")
def fixture_mock_update_data_item(mocker: MockerFixture):
    """Fixture for mocking update_data_item."""
    return mocker.patch("ska_dlm.data_item.data_item_requests.update_data_item")


@pytest.fixture(name="mock_notify_data_dashboard")
def fixture_mock_notify_data_dashboard(mocker: MockerFixture):
    """Fixture for mocking notify_data_dashboard."""
    return mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.notify_data_dashboard", return_value=True
    )


def test_register_data_item(
    caplog, mock_init_data_item, mock_update_data_item, mock_notify_data_dashboard
):
    """Test the registration of a data item with provided client metadata."""
    caplog.set_level(logging.INFO)

    metadata = {"execution_block": "eb123"}  # Client-provided metadata
    item_name = "test-item"
    uri = "test-uri"

    dlm_ingest.register_data_item(metadata=metadata, item_name=item_name, uri=uri)

    # Assert: No warnings or errors in logs
    for record in caplog.records:
        assert record.levelname not in [
            "WARNING",
            "ERROR",
        ], f"Unexpected log level {record.levelname}: {record.message}"

    assert mock_init_data_item.call_count == 1
    assert mock_update_data_item.call_count > 1
    mock_update_data_item.assert_any_call(
        uid="test-uid",
        post_data={
            "metadata": {"execution_block": "eb123", "uid": "test-uid", "item_name": "test-item"}
        },
    )
    assert mock_notify_data_dashboard.call_count == 1  # TODO: don't notify DPD via REST


# TODO: all the notify_data_dashboard tests could use updating
def test_notify_data_dashboard(caplog):
    """Test that the write hook will post metadata file info to a URL."""
    with Mocker() as req_mock:
        assert isinstance(req_mock, Mocker)
        # mock the HTTP response from the URL /ingestnewmetadata
        # based on the normal response from ska-sdp-dataproduct-api
        req_mock.post(
            CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata",
            text="New data product metadata file loaded and store index updated",
            status_code=200,
        )
        dlm_ingest.notify_data_dashboard({"execution_block": "block123"})

    assert not any(record.levelno == logging.ERROR for record in caplog.records), caplog.text
    assert "POSTed metadata (execution_block: block123) to" in caplog.text


@pytest.mark.parametrize(
    "metadata", ["invalid metadata", {"invalid": "metadata"}, Path("invalid metadata"), None]
)
def test_notify_data_dashboard_invalid_metadata(metadata, caplog):
    """Test notify_data_dashboard with invalid metadata."""
    with Mocker() as req_mock:
        assert isinstance(req_mock, Mocker)
        req_mock.post(
            CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata",
            text="New data product metadata file loaded and store index updated",
            status_code=200,
        )
        dlm_ingest.notify_data_dashboard(metadata)

    assert any(record.levelno == logging.ERROR for record in caplog.records), caplog.text
    assert "Failed to parse metadata" in caplog.text


def test_notify_data_dashboard_exception_response(caplog):
    """Test notify_data_dashboard POST error."""
    valid_metadata = {"execution_block": "block123"}
    with Mocker() as req_mock:
        assert isinstance(req_mock, Mocker)
        req_mock.post(
            CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata",
            exc=requests.RequestException("Mock request exception"),
        )
        dlm_ingest.notify_data_dashboard(valid_metadata)

    assert any(record.levelno == logging.ERROR for record in caplog.records), caplog.text
    assert "POST error notifying dataproduct dashboard at" in caplog.text


@pytest.mark.parametrize("status_code", [400, 404, 500, 503])
def test_notify_data_dashboard_http_errors(status_code, caplog):
    """Test that the write hook will post metadata file info to a URL."""
    valid_metadata = {"execution_block": "block123"}
    with Mocker() as req_mock:
        assert isinstance(req_mock, Mocker)
        req_mock.post(
            CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata",
            text="Mock response",
            status_code=status_code,
        )
        dlm_ingest.notify_data_dashboard(valid_metadata)

    assert any(record.levelno == logging.ERROR for record in caplog.records), caplog.text
    assert "POST error notifying dataproduct dashboard at" in caplog.text, caplog.text
