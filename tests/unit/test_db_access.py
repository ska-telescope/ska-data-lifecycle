"""DB Access tests."""

import pytest

from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB


# pylint: disable=unused-argument
@pytest.fixture(name="mock_db")
def mock_database_fixture(env):
    """Mock database fixture."""
    # NOTE: postgrest service required
    yield


def test_query_expired():
    """Test the query expired returning records."""
    res = DB.select(CONFIG.DLM.dlm_table, params={"limit": 1000})
    assert isinstance(res, list)
