"""Unit tests for dlm_ingest."""

import logging
import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from ska_dlm import dlm_ingest
from ska_dlm.dlm_ingest.dlm_ingest_requests import UpdateDataItemRequest, _get_ingest_session
from ska_dlm.dlm_ingest.dlm_ingest_requests import rest as ingest_rest
from ska_dlm.dlm_ingest.dlm_ingest_requests import update_data_item_children
from ska_dlm.exceptions import UnmetPreconditionForOperation, ValueAlreadyInDB


@pytest.fixture(name="mock_ingest_requests_storage", autouse=True)
def fixture_mock_ingest_requests_storage(mocker: MockerFixture):
    """Fixture to mock all storage related calls used in dlm_ingest_requests."""
    mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.query_storage",
        return_value=[
            {
                "storage_id": uuid.uuid4(),
                "storage_phase": "some-phase-level",
                "root_directory": "/root/",
            }
        ],
    )
    mocker.patch("ska_dlm.dlm_storage.dlm_storage_requests.rclone_access", return_value=True)
    mocker.patch("ska_dlm.dlm_ingest.dlm_ingest_requests.check_storage_access", return_value=True)


@pytest.fixture(name="mock_storage_rclone_access_false")
def fixture_mock_storage_rclone_access_false(mocker: MockerFixture):
    """Fixture to mock call to rclone access testing false."""
    return mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.check_storage_access", return_value=False
    )


@pytest.fixture(name="mock_query_data_item")
def fixture_mock_query_data_item(mocker: MockerFixture):
    """Hack to make register_data_item return early."""
    return mocker.patch(
        "ska_dlm.dlm_ingest.dlm_ingest_requests.query_data_item", return_value=True
    )


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


class _FakeSessionTransaction:
    """Minimal async transaction context manager for endpoint tests."""

    async def __aenter__(self):
        """Enter the fake transaction."""
        return self

    async def __aexit__(self, *_exc_info):
        """Exit the fake transaction."""
        return False


class _FakeResult:
    """Minimal SQLAlchemy result containing inserted row IDs."""

    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        """Return the fake scalar result."""
        return self

    def all(self):
        """Return all fake rows."""
        return self.rows


class _FakeSession:
    """Capture SQLAlchemy statements without connecting to a database."""

    def __init__(self, inserted_ids, existing_uids=(), execute_error=None):
        self.inserted_ids = inserted_ids
        self.existing_uids = existing_uids
        self.execute_error = execute_error
        self.statement = None

    def begin(self):
        """Start a fake transaction."""
        return _FakeSessionTransaction()

    async def scalars(self, _statement):
        """Return the data item UUIDs present in the fake database."""
        return _FakeResult(self.existing_uids)

    async def execute(self, statement):
        """Capture the SQLAlchemy statement and return fake inserted IDs."""
        self.statement = statement
        if self.execute_error:
            raise self.execute_error
        return _FakeResult(self.inserted_ids)


def test_register_data_item(caplog, mock_init_data_item, mock_update_data_item):
    """Test the registration of a data item with provided client metadata."""
    caplog.set_level(logging.INFO)

    metadata = {"execution_block": "eb123"}  # Client-provided metadata
    item_name = "test-item"
    uri = "test-uri"
    oid_expiration = datetime(2099, 12, 31, 23, 59, 59)

    dlm_ingest.register_data_item(
        metadata=metadata, item_name=item_name, uri=uri, oid_expiration=oid_expiration
    )

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


def test_register_data_item_no_rclone_access(
    mock_storage_rclone_access_false, mock_query_data_item
):
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
    assert mock_query_data_item.call_count == 1


@pytest.mark.asyncio
async def test_update_data_item_children_inserts_unique_child_associations():
    """Insert the requested parent/child pairs idempotently."""
    parent_uuid = uuid.uuid4()
    first_child_uuid = uuid.uuid4()
    second_child_uuid = uuid.uuid4()
    session = _FakeSession(
        [uuid.uuid4(), uuid.uuid4()],
        existing_uids=[parent_uuid, first_child_uuid, second_child_uuid],
    )

    result = await update_data_item_children(
        UpdateDataItemRequest(
            parent_data_item_uid=parent_uuid,
            children=[first_child_uuid, first_child_uuid, second_child_uuid],
        ),
        session,
    )

    assert result.inserted_count == 2
    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert "ON CONFLICT ON CONSTRAINT uq_data_item_children_parent_child DO NOTHING" in str(
        compiled
    )
    assert len(compiled.params) == 4
    assert set(compiled.params.values()) == {parent_uuid, first_child_uuid, second_child_uuid}


@pytest.mark.asyncio
async def test_update_data_item_children_with_no_children_does_not_execute():
    """Do not issue a database insert for an empty child list."""
    parent_uuid = uuid.uuid4()
    session = _FakeSession([], existing_uids=[parent_uuid])

    result = await update_data_item_children(
        UpdateDataItemRequest(parent_data_item_uid=parent_uuid, children=[]),
        session,
    )

    assert result.inserted_count == 0
    assert session.statement is None


@pytest.mark.asyncio
async def test_update_data_item_children_returns_404_for_missing_items():
    """Report missing parent or child UUIDs as a client error."""
    parent_uuid = uuid.uuid4()
    missing_child_uuid = uuid.uuid4()
    session = _FakeSession([], existing_uids=[parent_uuid])

    with pytest.raises(HTTPException) as exc_info:
        await update_data_item_children(
            UpdateDataItemRequest(
                parent_data_item_uid=parent_uuid,
                children=[missing_child_uuid],
            ),
            session,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["missing_uids"] == [str(missing_child_uuid)]


@pytest.mark.asyncio
async def test_update_data_item_children_returns_409_for_integrity_conflict():
    """Map a database integrity race to a conflict response."""
    parent_uuid = uuid.uuid4()
    child_uuid = uuid.uuid4()
    session = _FakeSession(
        [],
        existing_uids=[parent_uuid, child_uuid],
        execute_error=IntegrityError("insert", {}, Exception("foreign key violation")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_data_item_children(
            UpdateDataItemRequest(
                parent_data_item_uid=parent_uuid,
                children=[child_uuid],
            ),
            session,
        )

    assert exc_info.value.status_code == 409


def test_update_data_item_children_is_available_as_fastapi_endpoint():
    """Expose update_data_item_children as a JSON FastAPI endpoint using ORM sessions."""
    parent_uuid = uuid.uuid4()
    child_uuid = uuid.uuid4()
    session = _FakeSession(
        [uuid.uuid4()],
        existing_uids=[parent_uuid, child_uuid],
    )

    async def override_session():
        yield session

    ingest_rest.dependency_overrides[_get_ingest_session] = override_session
    client = TestClient(ingest_rest)
    try:
        response = client.post(
            "/ingest/update_data_item_children",
            json={
                "parent_data_item_uid": str(parent_uuid),
                "children": [str(child_uuid)],
            },
        )
    finally:
        ingest_rest.dependency_overrides.pop(_get_ingest_session, None)

    assert response.status_code == 200
    assert response.json() == {"inserted_count": 1}
