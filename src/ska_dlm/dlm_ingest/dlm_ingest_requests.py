"""Convenience functions wrapping the most important postgREST API calls."""

import json
import logging

from ska_dlm.dlm_storage.dlm_storage_requests import rclone_access

from .. import CONFIG
from ..data_item import set_state, set_uri
from ..dlm_db.db_access import DB
from ..dlm_request import query_data_item, query_exists
from ..dlm_storage import check_storage_access, query_storage
from ..exceptions import InvalidQueryParameters, UnmetPreconditionForOperation, ValueAlreadyInDB

logger = logging.getLogger(__name__)


def init_data_item(item_name: str = "", json_data: str = "") -> str:
    """
    Intialize a new data_item by at least specifying an item_name.

    Parameters:
    -----------
    item_name, the item_name, can be empty, but then json_data has to be specified.
    json_data, provides to ability to specify all values.

    Returns:
    --------
    uid,
    """
    if item_name:
        post_data = {"item_name": item_name}
    elif json_data:
        post_data = json.loads(json_data)
    else:
        raise InvalidQueryParameters("Either item_name or json_data has to be specified!")
    return DB.insert(CONFIG.DLM.dlm_table, json=post_data)[0]["uid"]


def ingest_data_item(
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
) -> str:
    """
    Ingest a data_item (register function is an alias).

    This high level function is a combination of init_data_item, set_uri and set_state(READY).
    It also checks whether a data_item is already registered on the requested storage.

    (1) check whether requested storage is known and accessible
    (2) check whether item is accessible/exists on that storage
    (3) check whether item is already registered on that storage
    (4) initialize the new item with the same OID on the new storage
    (5) set state to READY

    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    uri: the access path to the payload.
    storage_name: the name of the configured storage volume (name or ID required)
    storage_id: optional, the ID of the configured storage.

    Returns:
    --------
    str, data_item UID
    """
    # (1)
    storages = query_storage(storage_name=storage_name, storage_id=storage_id)
    if not storages:
        raise UnmetPreconditionForOperation(
            f"No storages found for {storage_name=}, {storage_id=}"
        )
    storage_id = storages[0]["storage_id"]
    if not check_storage_access(storage_name=storage_name, storage_id=storage_id):
        raise UnmetPreconditionForOperation(
            f"Requested storage volume is not accessible by DLM! {storage_name}"
        )
    # (2)
    if not rclone_access(storage_name, uri):
        raise UnmetPreconditionForOperation(f"File {uri} does not exist on {storage_name}")
    if query_exists(item_name):
        ex_storage_id = query_data_item(item_name)[0]["storage_id"]
        if storage_id == ex_storage_id:
            raise ValueAlreadyInDB(f"Item is already registered on storage! {item_name=}")
    # (3)
    init_item = {
        "item_name": item_name,
        "storage_id": storage_id,
    }
    uid = init_data_item(json_data=json.dumps(init_item))
    # (4)
    set_uri(uid, uri, storage_id)
    # all done! Set data_item state to READY
    set_state(uid, "READY")
    return uid


# just for convenience we also define the ingest function as register_data_item.
register_data_item = ingest_data_item
