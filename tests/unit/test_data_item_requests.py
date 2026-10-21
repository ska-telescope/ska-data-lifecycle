"""Unit tests for data-item request endpoints."""

import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from ska_dlm.data_item import data_item_requests
from ska_dlm.dlm_db import DataItem


class _ScalarResult:  # pylint: disable=too-few-public-methods
    """Minimal scalar result for mocked SQLAlchemy executions."""

    def __init__(self, rows):
        self.rows = rows

    def first(self):
        """Return the first scalar row."""
        return self.rows[0] if self.rows else None


class _Result:
    """Minimal SQLAlchemy result with scalar and mapping access."""

    def __init__(self, scalar_rows=(), mapping_rows=()):
        self.scalar_rows = scalar_rows
        self.mapping_rows = mapping_rows

    def scalars(self):
        """Return scalar access for ORM selects."""
        return _ScalarResult(self.scalar_rows)

    def mappings(self):
        """Return mapping access for projected child selects."""
        return self

    def all(self):
        """Return all projected rows."""
        return self.mapping_rows


class _Session:  # pylint: disable=too-few-public-methods
    """Provide queued SQLAlchemy results without a database connection."""

    def __init__(self, *results):
        self.results = list(results)
        self.statements = []

    async def execute(self, statement):
        """Return the next queued result or raise the queued exception."""
        self.statements.append(statement)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture(name="client_factory")
def fixture_client_factory() -> Callable:
    """Create a test client with an injected async session."""

    def create_client(session):
        app = FastAPI()
        app.include_router(data_item_requests.rest)

        async def override_session():
            yield session

        app.dependency_overrides[
            data_item_requests._get_data_item_session  # pylint: disable=protected-access
        ] = override_session
        return TestClient(app)

    return create_client


def _data_item(oid: uuid.UUID, item_type: str = "file") -> DataItem:
    """Build a minimal ORM item for endpoint tests."""
    return DataItem(
        UID=uuid.uuid4(),
        OID=oid,
        item_type=item_type,
        item_name="test-item",
    )


def test_item_first_match(client_factory):
    """Return the first ORM row matching an OID."""
    oid = uuid.uuid4()
    first = _data_item(oid)
    second = _data_item(oid)
    client = client_factory(_Session(_Result(scalar_rows=[first, second])))

    response = client.get("/request/get_data_item", params={"oid": str(oid)})

    assert response.status_code == 200
    assert response.json()["uid"] == str(first.UID)
    assert response.json()["children"] is None


def test_container_children(client_factory):
    """Return immediate child identity fields for a container."""
    oid = uuid.uuid4()
    parent = _data_item(oid, item_type="container")
    child = {
        "uid": str(uuid.uuid4()),
        "oid": str(uuid.uuid4()),
        "item_name": "child",
    }
    session = _Session(_Result(scalar_rows=[parent]), _Result(mapping_rows=[child]))
    client = client_factory(session)

    response = client.get("/request/get_data_item", params={"oid": str(oid)})

    assert response.status_code == 200
    assert response.json()["children"] == [child]
    child_query = str(session.statements[1].compile(dialect=postgresql.dialect()))
    assert "JOIN dlm.data_item_children" in child_query
    assert "dlm.data_item_children.parent_data_item_uid" in child_query
    assert (
        parent.UID in session.statements[1].compile(dialect=postgresql.dialect()).params.values()
    )


def test_item_not_found(client_factory):
    """Return 404 when the OID has no data item."""
    client = client_factory(_Session(_Result()))

    response = client.get("/request/get_data_item", params={"oid": str(uuid.uuid4())})

    assert response.status_code == 404
    assert response.json()["detail"]["exec"] == "DataItemNotFound"


def test_children_error(client_factory):
    """Map child-link query failures to HTTP 500."""
    oid = uuid.uuid4()
    parent = _data_item(oid, item_type="container")
    child_error = SQLAlchemyError("child query failed")
    client = client_factory(_Session(_Result(scalar_rows=[parent]), child_error))

    response = client.get("/request/get_data_item", params={"oid": str(oid)})

    assert response.status_code == 500
    assert response.json()["detail"]["exec"] == "SQLAlchemyError"


def test_empty_children(client_factory):
    """Return an empty child list when there are no child links."""
    oid = uuid.uuid4()
    parent = _data_item(oid, item_type="container")
    client = client_factory(_Session(_Result(scalar_rows=[parent]), _Result(mapping_rows=[])))

    response = client.get("/request/get_data_item", params={"oid": str(oid)})

    assert response.status_code == 200
    assert response.json()["children"] == []


def test_database_error(client_factory):
    """Map SQLAlchemy failures to HTTP 500."""
    client = client_factory(_Session(SQLAlchemyError("database unavailable")))

    response = client.get("/request/get_data_item", params={"oid": str(uuid.uuid4())})

    assert response.status_code == 500
    assert response.json()["detail"]["exec"] == "SQLAlchemyError"


def test_invalid_oid(client_factory):
    """Reject malformed UUID query parameters."""
    client = client_factory(_Session())

    response = client.get("/request/get_data_item", params={"oid": "not-a-uuid"})

    assert response.status_code == 422
