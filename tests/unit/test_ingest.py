"""Unit tests for dlm_ingest."""

import logging
import uuid

import pytest
from pytest_mock import MockerFixture

from ska_dlm import dlm_ingest
from ska_dlm.exceptions import UnmetPreconditionForOperation, ValueAlreadyInDB


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


@pytest.fixture(name="mock_storage_rclone_access_false")
def fixture_mock_storage_rclone_access_false(mocker: MockerFixture):
    """Fixture to mock call to rclone access testing false."""
    mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.check_storage_access", return_value=False)
    # Hack to make register_data_item return early
    mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.query_data_item", return_value=True)


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


def test_register_data_item(caplog, mock_init_data_item, mock_update_data_item):
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


def test_register_data_item_no_rclone_access(mock_storage_rclone_access_false):
    """Test the registration of a data item with no rclone/storage access."""

    metadata = {"execution_block": "eb123"}  # Client-provided metadata
    item_name = "test-item"
    uri = "test-uri"

    try:
        dlm_ingest.register_data_item(metadata=metadata, item_name=item_name, uri=uri)
        assert False
    except UnmetPreconditionForOperation:
        assert True

    try:
        # In this case we mock the call after the check for storage access to return
        # from the method early. This forces the ValueAlreadyInDB exception...
        dlm_ingest.register_data_item(
            metadata=metadata, item_name=item_name, uri=uri, do_storage_access_check=False
        )
        assert False
    except ValueAlreadyInDB:
        assert True

    # Assert that the check_storage_access mock was called
    assert mock_storage_rclone_access_false.call_count == 1
