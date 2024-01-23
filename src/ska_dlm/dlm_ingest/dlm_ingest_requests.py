"""Convenience functions wrapping the most important postgREST API calls."""
import json
import logging

import requests

from .. import CONFIG

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
    return request.json()[0]["uid"]


def update_data_item(
    oid: str = "", uid: str = "", json_data: str = "", table: str = CONFIG.DLM.dlm_table
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
        logger.warning("Nothing updated using this request: %s : %s", request_url, post_data)
        logger.warning("Status code: %s", request.status_code)
        result = ""
    else:
        result = request.json()[0]["uid"]
    return result


def set_uri(uid: str, uri: str) -> str:
    """
    Set the URI field of the uid data_item.

    Parameters:
    -----------
    uid : the uid of the data_item to be updated
    uri : the access URI for the data_item

    Returns:
    --------
    string
    """
    json_data = json.dumps({"uri": uri})
    res = update_data_item(uid=uid, json_data=json_data)
    return res


def set_state(uid: str, state: str) -> str:
    """
    Set the state field of the uid data_item.

    Parameters:
    -----------
    uid : the uid of the data_item to be updated
    state : the new state for the data_item

    Returns:
    --------
    string
    """
    json_data = json.dumps({"state": state})
    res = update_data_item(uid=uid, json_data=json_data)
    return res


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
