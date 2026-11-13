"""DB Access tests."""

import pytest

from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB, PostgRESTAccess


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


def test_insert_forwards_params_and_headers(mocker):
    """Allow inserts to specify PostgREST conflict handling."""
    session = mocker.Mock()
    response = mocker.Mock()
    response.json.return_value = []
    session.request.return_value = response
    mocker.patch("ska_dlm.dlm_db.db_access.requests.Session", return_value=session)

    with PostgRESTAccess("http://example.test") as db:
        params = {"on_conflict": "parent_data_item_uuid,data_item_uid"}
        headers = {
            "Prefer": "resolution=ignore-duplicates, missing=default, return=representation"
        }

        assert db.insert("data_item_children", json=[], params=params, headers=headers) == []

        session.request.assert_called_once_with(
            "POST",
            "http://example.test/data_item_children",
            params=params,
            json=[],
            timeout=10,
            headers=headers,
        )
