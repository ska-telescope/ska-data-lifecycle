"""dlm_migration REST client."""

import requests

from tests.integration.client.exception_handler import dlm_raise_for_status

MIGRATION_URL = ""
TOKEN: str = None


def copy_data_item(
    # pylint: disable=too-many-arguments,unused-argument,too-many-positional-arguments
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    destination_name: str = "",
    destination_id: str = "",
    path: str = "",
) -> dict:
    """Copy a data_item from source to destination.

    Steps
    (1) get the current storage_id(s) of the item
    (2) convert one (first) storage_id to a configured rclone backend
    (3) initialize the new item with the same OID on the new storage
    (4) use the rclone copy command to copy it to the new location
    (5) set the access path to the payload
    (6) set state to 'ready'
    (7) save metadata in the data_item table


    Parameters
    ----------
    item_name
        data item name, when empty the first 1000 items are returned, by default ""
    oid
        object id, Return data_items referred to by the OID provided, by default ""
    uid
        Return data_item referred to by the UID provided, by default ""
    destination_name
        the name of the destination storage volume, by default ""
    destination_id
        the destination storage, by default ""
    path
        the destination path relative to storage root, by default ""

    Returns
    -------
    dict
        uid: The uid of the new item copy.
        migration_id: Migration ID used to check current migration status of copy.

    Raises
    ------
    InvalidQueryParameters
        Neither an item_name, OID nor UID parameter provided.
    UnmetPreconditionForOperation
        No data item found for copying.
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{MIGRATION_URL}/migration/copy_data_item", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


def query_migrations(
    # pylint: disable=unused-argument
    start_date: str | None = None,
    end_date: str | None = None,
    storage_id: str | None = None,
) -> list[dict]:
    """
    Query for all migrations by a given user, with optional filters.

    Parameters
    ----------
    start_date
        Filter migrations that started after this date (YYYY-MM-DD or YYYYMMDD)
    end_date
        Filter migrations that ended before this date (YYYY-MM-DD or YYYYMMDD)
    storage_id
        Filter migrations by a specific storage location

    Returns
    -------
    list[dict]
        migrations
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{MIGRATION_URL}/migration/query_migrations", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


def get_migration_record(migration_id: int) -> list:
    # pylint: disable=unused-argument
    """Query for a specific migration.

    Parameters
    ----------
    migration_id
        Migration id of migration

    Returns
    -------
    list
        list of matching migrations
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{MIGRATION_URL}/migration/get_migration", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()
