import json
import logging
from pathlib import Path

import pytest
import requests
from requests_mock import Mocker
from ska_sdp_dataproduct_metadata import MetaData

from ska_dlm import CONFIG, dlm_ingest


def test_metadata_provided_by_client(mocker):
    # Mock the rclone_access function to bypass access checks
    mock_rclone_access = mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.rclone_access", return_value=True
    )

    # Mock the functions that interact with the database
    mock_set_uri = mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.set_uri")
    mock_update_data_item = mocker.patch("ska_dlm.data_item.data_item_requests.update_data_item")

    # Mock the remaining parts
    mock_init_data_item = mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.init_data_item")
    mock_set_metadata = mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.set_metadata")
    mock_logger = mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.logger")

    # Scenario 1: Metadata is provided by the client
    metadata = {"key": "value"}
    item_name = "test-item"
    uri = "test-uri"

    # Call the function
    dlm_ingest.register_data_item(metadata=metadata, item_name=item_name, uri=uri)

    # Assertions
    mock_rclone_access.assert_called_once_with(
        "", uri
    )  # Ensure rclone was called and mocked correctly
    mock_logger.info.assert_called_once_with("Saved metadata provided by client.")
    mock_set_metadata.assert_called_once_with(mock_init_data_item.return_value, metadata)
    mock_init_data_item.assert_called_once_with(
        json_data='{"item_name": "test-item", "storage_id": "efd23df9-fc0c-44ac-a817-ddc66ad30f36", "item_phase": "GAS", "item_format": "unknown", "item_owner": null}'
    )

    # Ensure database-related methods were mocked and not executed
    mock_set_uri.assert_called_once_with(mock_init_data_item.return_value, uri, mocker.ANY)
    # set metadata function calls update_data_item function
    mock_update_data_item.assert_called_once_with(
        uid=mock_init_data_item.return_value, post_data={"item_state": "READY"}
    )


def test_notify_data_dashboard(caplog):
    """Test that the write hook will post metadata file info to a URL."""
    with Mocker() as req_mock:
        assert isinstance(req_mock, Mocker)
        # mock a response for the URL notify_data_dashboard requests
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
