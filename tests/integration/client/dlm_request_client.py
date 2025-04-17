"""dlm_request REST client."""

from datetime import timedelta

import requests

from tests.integration.client.exception_handler import dlm_raise_for_status

REQUEST_URL = ""
TOKEN = None


# pylint: disable=unused-argument
def query_expired(offset: timedelta | None = None):
    """
    Query for all expired data_items using the uid_expiration timestamp.

    Parameters
    ----------
    offset
        optional offset for the query
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{REQUEST_URL}/request/query_expired", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument
def query_deleted(uid: str = "") -> list[dict]:
    """Query for all deleted data_items using the deleted state.

    Parameters
    ----------
    uid
        The UID to be checked, optional.

    Returns
    -------
    list[dict]
        list of dictionaries with UIDs of deleted items.
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{REQUEST_URL}/request/query_deleted", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument
def query_new(check_date: str, uid: str = "") -> list:
    """Query for all data_items newer than the date provided.

    Parameters
    ----------
    check_date
        the UTC starting date (exclusive)
    uid
        The UID to be checked, optional.

    Returns
    -------
    list
        list of dictionaries with UID, UID_creation and storage_id of new items.
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{REQUEST_URL}/request/query_new", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


def query_exists(item_name: str = "", oid: str = "", uid: str = "", ready: bool = False) -> bool:
    """Query to check for existence of a data_item.

    Parameters
    ----------
    item_name
        optional item_name
    oid
        the oid to be searched for
    uid
        this returns only one storage_id
    ready
        whether the item must be in ready state.

    Returns
    -------
    bool
        True if the data_item exists
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{REQUEST_URL}/request/query_exists", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument
def query_exists_and_ready(item_name: str = "", oid: str = "", uid: str = "") -> bool:
    """Check whether a data_item exists and is in ready state.

    Parameters
    ----------
    item_name
        optional item_name
    oid
        the oid to be searched for
    uid
        this returns only one storage_id

    Returns
    -------
    bool
        True if the item exists and is in ready state
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{REQUEST_URL}/request/query_exist_and_ready", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument
def query_item_storage(item_name: str = "", oid: str = "", uid: str = "") -> list[dict]:
    """Query for the storage_ids of all backends holding a copy of a data_item.

    Either an item_name or a OID have to be provided.

    Parameters
    ----------
    item_name
        optional item_name
    oid
        the oid to be searched for
    uid
        this returns only one storage_id

    Returns
    -------
    list[dict]
        list of storage_ids
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{REQUEST_URL}/request/query_item_storage", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()
