"""dlm_migration REST client"""

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
) -> str:
    """Copy a data_item from source to destination.

    Steps
    (1) get the current storage_id(s) of the item
    (2) convert one (first) storage_id to a configured rclone backend
    (3) initialize the new item with the same OID on the new storage
    (4) use the rclone copy command to copy it to the new location
    (5) set the access path to the payload
    (6) set state to READY
    (7) save metadata in the data_item table


    Parameters
    ----------
    item_name : str
        data item name, when empty the first 1000 items are returned, by default ""
    oid : str
        object id, Return data_items referred to by the OID provided, by default ""
    uid : str
        Return data_item referred to by the UID provided, by default ""
    destination_name : str
        the name of the destination storage volume, by default ""
    destination_id : str
        the destination storage, by default ""
    path : str
        the destination path relative to storage root, by default ""
    authorization : str, optional
        Validated Bearer token with UserInfo

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


def query_migrations() -> list[dict]:
    """Query for all migrations by a given user.

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
    """
    Query for a specific migration.

    Parameters
    ----------
    migration_id : int
        Migration id of migration

    Returns
    -------
    list
    """

    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{MIGRATION_URL}/migration/get_migration", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()
