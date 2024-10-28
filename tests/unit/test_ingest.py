"""Unit tests for dlm_ingest."""

import json
import logging
from pathlib import Path

import pytest
import requests
from requests_mock import Mocker

from ska_dlm import CONFIG, dlm_ingest


@pytest.fixture
def patched_dependencies(mocker):
    """Fixture for the mocker.patch calls."""
    mock_init_data_item = mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.init_data_item", return_value="test-uid"
    )
    mock_update_data_item = mocker.patch("ska_dlm.data_item.data_item_requests.update_data_item")
    mock_rclone_access = mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.rclone_access", return_value=True
    )
    mock_query_storage = mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.query_storage",
        return_value=[{"storage_id": "storage-id", "storage_phase_level": "some-phase-level"}],
    )
    mock_check_storage_access = mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.check_storage_access", return_value=True
    )
    mock_notify_data_dashboard = mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.notify_data_dashboard", return_value=True
    )
    mock_scrape_metadata = mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.scrape_metadata",
        return_value={"execution_block": "scraped_value"},
    )
    mock_generate_metadata = mocker.patch(
        "ska_sdp_metadata_generator.generate_metadata_from_generator",
        side_effect=lambda uri, eb_id: mocker.Mock(
            get_data=lambda: mocker.Mock(to_json=lambda: json.dumps({"key": "value"}))
        ),
    )

    return {
        "mock_init_data_item": mock_init_data_item,
        "mock_update_data_item": mock_update_data_item,
        "mock_rclone_access": mock_rclone_access,
        "mock_query_storage": mock_query_storage,
        "mock_check_storage_access": mock_check_storage_access,
        "mock_notify_data_dashboard": mock_notify_data_dashboard,
        "mock_scrape_metadata": mock_scrape_metadata,
        "mock_generate_metadata": mock_generate_metadata,
    }


def test_register_data_item_with_client_metadata(caplog, patched_dependencies):
    # pylint: disable=redefined-outer-name
    """Test the registration of a data item with provided client metadata."""
    caplog.set_level(logging.INFO)

    mocks = patched_dependencies

    metadata = {"execution_block": "eb123"}  # Client-provided metadata
    item_name = "test-item"
    uri = "test-uri"

    dlm_ingest.register_data_item(metadata=metadata, item_name=item_name, uri=uri)

    assert "Saved metadata provided by client." in caplog.text

    # Assert: No warnings or errors in logs
    for record in caplog.records:
        assert record.levelname not in [
            "WARNING",
            "ERROR",
        ], f"Unexpected log level {record.levelname}: {record.message}"

    assert mocks["mock_update_data_item"].call_count > 1
    mocks["mock_update_data_item"].assert_any_call(
        uid="test-uid",
        post_data={
            "metadata": {"execution_block": "eb123", "uid": "test-uid", "item_name": "test-item"}
        },
    )


def test_register_data_item_no_client_metadata(patched_dependencies):
    # pylint: disable=redefined-outer-name
    """Test register_data_item with no client-provided metadata; metadata scraper is called."""
    mocks = patched_dependencies

    item_name = "test-item"
    uri = "test-uri"
    eb_id = None  # Simulate missing eb_id from the client

    # Call the function with no client metadata and no eb_id
    dlm_ingest.register_data_item(metadata=None, item_name=item_name, uri=uri, eb_id=eb_id)

    # Assert that scrape_metadata is called by register_data_item
    mocks["mock_scrape_metadata"].assert_called_once_with(uri, eb_id)

    assert mocks["mock_update_data_item"].call_count > 1
    mocks["mock_update_data_item"].assert_any_call(
        uid="test-uid",
        post_data={
            "metadata": {
                "execution_block": "scraped_value",
                "uid": "test-uid",
                "item_name": "test-item",
            },
        },
    )


@pytest.mark.parametrize(
    "input_args, expected_result, expected_log",
    [
        (["test-uri", "eb123"], {"key": "value"}, "Metadata extracted successfully."),
        (["test-uri", None], {"key": "value"}, "Metadata extracted successfully."),
    ],
)
def test_scrape_metadata(patched_dependencies, caplog, input_args, expected_result, expected_log):
    """Test that scrape_metadata returns correct logs and results for different cases."""
    caplog.set_level(logging.INFO)

    patched_dependencies["mock_generate_metadata"]
    result = dlm_ingest.scrape_metadata(*input_args)

    assert result == expected_result
    assert expected_log in caplog.text

    # Assert: No warnings or errors in logs
    for record in caplog.records:
        assert record.levelname not in [
            "WARNING",
            "ERROR",
        ], f"Unexpected log level {record.levelname}: {record.message}"

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
