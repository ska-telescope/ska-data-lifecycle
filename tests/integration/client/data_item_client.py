"""data_item_request REST client."""

import requests

from ska_dlm.typer_types import JsonObjectOption
from tests.integration.client.exception_handler import dlm_raise_for_status

REQUEST_URL = ""
TOKEN = None


# pylint: disable=unused-argument
def query_data_item(
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    storage_id: str = "",
    params: str | None = None,  # TODO: meant to be dict | None
) -> list[dict]:
    """Query a data_item.

    params or item_name/oid/uid is required.

    Parameters
    ----------
    item_name
        Could be empty, in which case the first 1000 items are returned
    oid
        Return data_items referred to by the OID provided.
    uid
        Return data_item referred to by the UID provided.
    storage_id
        Return data_item referred to by a given storage_id.
    params
        specify the query parameters

    Returns
    -------
    list[dict]
        data item ids.
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{REQUEST_URL}/request/query_data_item", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


def update_data_item(
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    post_data: JsonObjectOption = None,
) -> dict:
    """Update fields of an existing data_item.

    This is mostly used by the other convenience functions. In general when specifying
    an OID or an item_name, multiple entries will be updated at the same time.

    Parameters
    ----------
    item_name
        the name of the data_items to be updated
    oid
        the OID of the data_items to be updated
    uid
        the UID of the data_item to be updated
    post_data
        the json formatted update data, compatible with postgREST

    Returns
    -------
    dict
        the updated data item entry

    Raises
    ------
    InvalidQueryParameters
        When neither item_name, oid or uid is given
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.patch(
        f"{REQUEST_URL}/request/update_data_item",
        params=params,
        headers=headers,
        json=post_data,
        timeout=60,
    )
    dlm_raise_for_status(response)
    return response.json()


def update_item_tags(
    item_name: str = "", oid: str = "", item_tags: JsonObjectOption = None
) -> dict:
    """
    Update/set the item_tags field of a data_item with given item_name/OID.

    This will update all records for a data_item at the same time.
    Updating a single UID does not make sense.

    Parameters
    ----------
    item_name
        the name of the data_item
    oid
        the OID of the data_item to be updated
    item_tags
        dictionary of keyword/value pairs

    Returns
    -------
    dict
        the updated data item entry
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.patch(
        f"{REQUEST_URL}/request/update_item_tags",
        params=params,
        headers=headers,
        json=item_tags,
        timeout=60,
    )
    dlm_raise_for_status(response)
    return response.json()
