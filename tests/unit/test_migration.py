"""Unit tests for dlm_migration."""

import pytest
from pytest_mock import MockerFixture

from ska_dlm import CONFIG, dlm_migration


@pytest.mark.parametrize(
    "start_date, end_date, storage_id, exp_params",
    [
        # Case 1: Only start_date given
        (
            "2022-01-01",
            None,
            None,
            {"limit": 1000, "user": "eq.testuser", "date": "gte.2022-01-01"},
        ),
        # Case 2: Start_date and end_date
        (
            "2022-01-01",
            "2024-01-01",
            None,
            {
                "limit": 1000,
                "user": "eq.testuser",
                "and": "(date.gte.2022-01-01,date.lte.2024-01-01)",
            },
        ),
        # Case 3: Start_date, end_date, and storage_id
        (
            "2022-01-01",
            "2024-01-01",
            "abcdef-1234",
            {
                "limit": 1000,
                "user": "eq.testuser",
                "and": "(date.gte.2022-01-01,date.lte.2024-01-01)",
                "or": "(source_storage_id.eq.abcdef-1234,destination_storage_id.eq.abcdef-1234)",
            },
        ),
    ],
)
def test_query_migrations(mocker: MockerFixture, start_date, end_date, storage_id, exp_params):
    """Test the `query_migrations` function with different filter combinations."""
    # Mock the DB.select method
    mock_db_select = mocker.patch("ska_dlm.dlm_db.db_access_sqlalchemy.DB.select")

    # Mock the decode_bearer function to return a valid username
    mock_decode_bearer = mocker.patch(
        "ska_dlm.dlm_migration.dlm_migration_requests.decode_bearer",
        return_value={"preferred_username": "testuser"},
    )

    # Call the function
    dlm_migration.query_migrations(
        start_date=start_date,
        end_date=end_date,
        storage_id=storage_id,
        authorization="Bearer some_fake_token",
    )

    # Ensure decode_bearer was called once
    mock_decode_bearer.assert_called_once()

    # Ensure DB.select was called with expected parameters
    mock_db_select.assert_called_once_with(CONFIG.DLM.migration_table, params=exp_params)
