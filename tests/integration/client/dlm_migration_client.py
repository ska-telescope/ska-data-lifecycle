"""dlm_migration REST client"""

import requests

MIGRATION_URL = ""
SESSION = None


def copy_data_item(  # pylint: disable=too-many-arguments, unused-argument
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
    (2) convert one(first) storage_id to a configured rclone backend
    (3) check whether item already exists on destination
    (4) initialize the new item with the same OID on the new storage
    (5) use the rclone copy command to copy it to the new location
    (6) make sure the copy was successful

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
        the destination path, by default ""

    Returns
    -------
    str
        The uid of the new item copy.

    Raises
    ------
    InvalidQueryParameters
        Neither an item_name, OID nor UID parameter provided.
    UnmetPreconditionForOperation
        No data item found for copying.
    """
    params = {k: v for k, v in locals().items() if v}
    response = SESSION.get(f"{MIGRATION_URL}/migration/copy_data_item", params=params, timeout=60)
    if response.status_code in [401, 403]:
        response.raise_for_status()
    return response.json()
