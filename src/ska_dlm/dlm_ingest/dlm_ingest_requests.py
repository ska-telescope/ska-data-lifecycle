"""Convenience functions wrapping the most important postgREST API calls."""
import json
import logging

import requests

from .. import CONFIG
from ..dlm_request import query_data_item, query_exists
from ..dlm_storage import (
    check_storage_access,
    query_storage,
)

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
    print(f">>>> {post_data}")
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

    It also checks whether a data_item is already registered in on the requested storage.

    (1) check whether requested storage is known and accessible
    (2) check whether item is already registered on that storage
    (3) initialize the new item with the same OID on the new storage
    (4) set state to READY

    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    uri: the access path to the payload.
    storage_name: the name of the configured storage volume (either the name or the ID
                  are required).
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


def update_data_item(
    oid: str = "",
    uid: str = "",
    json_data: str = "",
    table: str = CONFIG.DLM.dlm_table,
) -> str:
    """
    Update fields of an existing data_item.

    This is mostly used by the other convenience functions.

    Parameters:
    -----------
    oid : the OID of the data_item to be updated
    uid : the UID of the data_item to be updated
    json_data : the json formatted update data, compatible with postgREST

    Returns:
    --------
    string
    """
    if oid:
        req_ext = f"oid=eq.{oid}"
    elif uid:
        req_ext = f"uid=eq.{uid}"
    else:
        logger.error("Either OID or UID should be specified!")
        return None
    request_url = f"{CONFIG.REST.base_url}/{table}?{req_ext}"
    post_data = json_data
    request = requests.patch(
        request_url,
        data=post_data,
        headers={
            "Content-type": "application/json",
            "Prefer": "missing=default, return=representation",
        },
        timeout=10,
    )
    if len(request.json()) == 0 or request.status_code not in [200, 201]:
        logger.warning(
            "Nothing updated using this request: %s : %s",
            request_url,
            post_data,
        )
        logger.warning("Status code: %s", request.status_code)
        result = ""
    else:
        result = request.json()[0]["uid"]
    return result


def set_uri(uid: str, uri: str, storage_id: str) -> bool:
    """
    Set the URI field of the uid data_item.

    Parameters:
    -----------
    uid : the uid of the data_item to be updated
    uri : the access URI for the data_item
    storage_id: the storage_id associated with the URI

    Returns:
    --------
    boolean, True if successful
    """
    json_data = json.dumps({"uri": uri, "storage_id": storage_id})
    res = update_data_item(uid=uid, json_data=json_data)
    return res != ""


def set_state(uid: str, state: str) -> bool:
    """
    Set the state field of the uid data_item.

    Parameters:
    -----------
    uid : the uid of the data_item to be updated
    state : the new state for the data_item

    Returns:
    --------
    boolean, True if successful
    """
    json_data = json.dumps({"item_state": state})
    res = update_data_item(uid=uid, json_data=json_data)
    return res != ""


def set_oid_expiration(oid: str, expiration: str) -> str:
    """
    Set the oid_expiration field of the data_items with the given OID.

    Parameters:
    -----------
    oid : the oid of the data_item to be updated
    expiration : the expiration date for the data_item

    Returns:
    --------
    string
    """
    json_data = json.dumps({"oid_expiration": expiration})
    res = update_data_item(oid=oid, json_data=json_data)
    return res


def set_uid_expiration(uid: str, expiration: str):
    """
    Set the uid_expiration field of the data_item with the given UID.

    Parameters:
    -----------
    uid : the UID of the data_item to be updated
    expiration : the expiration date for the data_item

    Returns:
    --------
    string
    """
    json_data = json.dumps({"uid_expiration": expiration})
    res = update_data_item(uid=uid, json_data=json_data)
    return res


def set_user(oid: str = "", uid: str = "", user: str = "SKA"):
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters:
    -----------
    oid : the OID of the data_item to be updated
    uid : the UID of the data_item to be updated
    user : the user for the data_item

    Returns:
    --------
    string
    """
    json_data = json.dumps({"user": user})
    if uid:
        res = update_data_item(uid=uid, json_data=json_data)
    elif oid:
        res = update_data_item(oid=oid, json_data=json_data)
    else:
        logger.error("Either OID or UID should be specified!")
        res = None
    return res


def set_group(oid: str = "", uid: str = "", group: str = "SKA"):
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters:
    -----------
    oid : the OID of the data_item to be updated
    uid : the UID of the data_item to be updated
    group : the group for the data_item

    Returns:
    --------
    string
    """
    json_data = json.dumps({"group": group})
    if uid:
        res = update_data_item(uid=uid, json_data=json_data)
    elif oid:
        res = update_data_item(oid=oid, json_data=json_data)
    else:
        logger.error("Either OID or UID should be specified!")
        res = None
    return res


def set_acl(oid: str = "", uid: str = "", acl: str = "{}"):
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters:
    -----------
    oid : the OID of the data_item to be updated
    uid : the UID of the data_item to be updated
    acl : the acl dict for the data_item

    Returns:
    --------
    string
    """
    json_data = json.dumps({"acl": acl})
    if uid:
        res = update_data_item(uid=uid, json_data=json_data)
    elif oid:
        res = update_data_item(oid=oid, json_data=json_data)
    else:
        logger.error("Either OID or UID should be specified!")
        res = None
    return res
