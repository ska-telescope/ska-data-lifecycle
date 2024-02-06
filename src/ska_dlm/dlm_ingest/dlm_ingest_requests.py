"""Convenience functions wrapping the most important postgREST API calls."""

import logging

import requests

from .. import CONFIG
from ..data_item import set_state, set_uri
from ..dlm_request import query_data_item, query_exists
from ..dlm_storage import check_storage_access, query_storage

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
    request_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.dlm_table}"
    if item_name:
        post_data = {"item_name": item_name}
    elif json_data:
        post_data = json_data
    else:
        logger.error("Either item_name or json_data has to be specified!")
        return None
    request = requests.post(
        request_url,
        json=post_data,
        headers={"Prefer": "missing=default, return=representation"},
        timeout=10,
    )
    if request.status_code not in [200, 201]:
        logger.warning(
            "Ingest unsuccessful! Status code: %d",
            request.status_code,
            exc_info=1,
        )
        return []
    return request.json()[0]["uid"]


def ingest_data_item(
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
) -> str:
    """
    Ingest a data_item.

    This high level function is a combination of init_data_item, set_uri and set_state(READY).
    It also checks whether a data_item is already registered on the requested storage.

    (1) check whether requested storage is known and accessible
    (2) check whether item is already registered on that storage
    (3) initialize the new item with the same OID on the new storage
    (4) set state to READY

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
    cont = True
    # (1)
    storages = query_storage(storage_name=storage_name, storage_id=storage_id)
    if not storages:
        cont = False
    storage_id = storages[0]["storage_id"]
    if cont and not check_storage_access(storage_name=storage_name, storage_id=storage_id):
        logger.error("Requested storage volume is not accessible by DLM! %s", storage_name)
        cont = False
    # (2)
    if cont and query_exists(item_name):
        ex_storage_id = query_data_item(item_name)[0]["storage_id"]
        if storage_id == ex_storage_id:
            logger.error("Item is already registered on storage! %s", item_name)
            return ""
    # (3)
    init_item = {
        "item_name": item_name,
        "storage_id": storage_id,
    }
    uid = init_data_item(json_data=init_item)
    # (4)
    stat = set_uri(uid, uri, storage_id)
    # all done! Set data_item state to READY
    stat = set_state(uid, "READY")
    return uid if stat else ""


# just for convenience we also define the ingest function as register_data_item.
register_data_item = ingest_data_item
