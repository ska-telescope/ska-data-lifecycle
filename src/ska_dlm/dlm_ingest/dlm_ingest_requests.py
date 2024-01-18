"""
Convenience functions wrapping the most important postgREST API calls. 
"""
import benedict
import json
import requests
from .. import CONFIG


def init_data_item(item_name: str = "", json_data: str = "") -> str:
    """
    Intialize a new data_item by at least specifying an item_name.

    Parameters:
    item_name, the item_name, can be empty, but then json_data has to be
               specified.
    json_data, provides to ability to specify all values.

    Returns:
    uid,
    """
    request_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.dlm_table}"
    if item_name:
        post_data = {"item_name": item_name}
    elif json_data:
        post_data = json_data
    else:
        print("Either item_name or json_data has to be specified!")
        return None
    r = requests.post(
        request_url, json=post_data, headers={"Prefer": "missing=default, return=representation"}
    )
    return r.json()[0]["uid"]


def set_uri(uid: str, uri: str):
    """ """
    pass


def set_state(uid: str, state):
    """ """
    pass


def set_oid_expiration(oid: str, expiration: str):
    """ """
    pass


def set_uid_expiration(uid: str, expiration: str):
    """ """
    pass


def set_user(oid: str = "", uid: str = "", user: str = "SKA"):
    """ """
    pass


def set_group(oid: str = "", uid: str = "", group: str = "SKA"):
    """ """
    pass


def set_acl(oid: str = "", uid: str = "", acl: str = "{}"):
    """ """
    pass
