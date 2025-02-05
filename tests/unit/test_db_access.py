"""DB Access tests."""

import pytest

from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB


def _clear_database():
    DB.delete(CONFIG.DLM.dlm_table)
    DB.delete(CONFIG.DLM.storage_config_table)
    DB.delete(CONFIG.DLM.storage_table)
    DB.delete(CONFIG.DLM.location_table)


@pytest.fixture(name="mock_db")
def mock_database_fixture(env):
    # NOTE: postgrest service required
    _clear_database()
    yield
    _clear_database()


def test_query_expired():
    """Test the query expired returning records."""
    res = DB.select(CONFIG.DLM.dlm_table, params={"limit": 1000})
    assert isinstance(res, list)
