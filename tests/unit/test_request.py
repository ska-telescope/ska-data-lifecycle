"""Unit tests for dlm_request."""

from datetime import timedelta

import inflect
import pytest

import ska_dlm.data_item as data_item
import ska_dlm.dlm_request.dlm_request_requests as dlm_request
from ska_dlm import CONFIG, dlm_ingest
from ska_dlm.dlm_db.db_access import DB


def _clear_database():
    DB.delete(CONFIG.DLM.dlm_table)
    DB.delete(CONFIG.DLM.storage_config_table)
    DB.delete(CONFIG.DLM.storage_table)
    DB.delete(CONFIG.DLM.location_table)


@pytest.fixture(name="mock_db")
def mock_database_fixture(env):
    """Mock database fixture."""
    # NOTE: postgrest service required
    _clear_database()
    yield
    _clear_database()


@pytest.fixture(name="mock_data_items")
def mock_data_items_fixture(mock_db):
    """Test data_item init."""
    engine = inflect.engine()
    success = True
    for i in range(1, 51, 1):
        ordinal = engine.number_to_words(engine.ordinal(i))
        uid = dlm_ingest.init_data_item(f"this/is/the/{ordinal}/test/item")
        if uid is None:
            success = False
    assert success


def test_query_expired(mock_data_items):
    """Test the query expired returning records."""
    uid = dlm_request.query_data_item()[0]["uid"]
    data_item.set_state(uid=uid, state="READY")
    assert len(dlm_request.query_expired(offset=timedelta(0))) == 0
    assert len(dlm_request.query_expired(offset=timedelta(days=1))) == 1


def test_query_expired_empty():
    """Test the query expired returning an empty set."""
    assert len(dlm_request.query_expired()) == 0
