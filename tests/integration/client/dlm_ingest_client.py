"""dlm_ingest REST client"""

from typing import Any, Dict, List, Union

import requests

from ska_dlm.typer_types import JsonObjectOption
from tests.integration.client.exception_handler import dlm_raise_for_status

INGEST_URL = ""
TOKEN: str = None

JsonType = Union[Dict[str, Any], List[Any], str, int, float, bool, None]


# pylint: disable=unused-argument
def init_data_item(item_name: str | None = None, phase: str = "GAS", json_data: str = "") -> str:
    """Initialize a new data_item.

    item_name or json_data is required.

    Parameters
    ----------
    item_name : str
        the item_name, can be empty, but then json_data has to be specified.
    phase : str
        the phase this item is set to (usually inherited from the storage)
    json_data : dict | None
        data item table values.

    Returns
    -------
    str
        created data_item UID

    Raises
    ------
    InvalidQueryParameters
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{INGEST_URL}/ingest/init_data_item", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument,too-many-arguments,too-many-positional-arguments
def register_data_item(
    item_name: str,
    uri: str = "",
    storage_name: str = "",
    storage_id: str = "",
    item_type: str | None = "unknown",
    parents: str | None = None,
    metadata: JsonObjectOption = None,
    eb_id: str | None = None,
) -> str:
    """Ingest a data_item (register function is an alias).

    This high level function is a combination of init_data_item, set_uri and set_state(READY).
    It also checks whether a data_item is already registered on the requested storage.

    (1) check whether requested storage is known and accessible
    (2) check whether item is accessible/exists on that storage
    (3) check whether item is already registered on that storage
    (4) initialize the new item with the same OID on the new storage
    (5) set state to READY
    (6) save metadata
    (7) notify the data dashboard

    Parameters
    ----------
    item_name: str
        could be empty, in which case the first 1000 items are returned
    uri : str
        the access path to the payload.
    storage_name: str
        the name of the configured storage volume (name or ID required)
    storage_id: str, optional
        the ID of the configured storage.
    metadata: dict, optional
        metadata provided by the client
    eb_id: str, optional
        execution block ID provided by the client

    Returns
    -------
    str
        created data_item UID

    Raises
    ------
    UnmetPreconditionForOperation
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{INGEST_URL}/ingest/register_data_item",
        params=params,
        json=metadata,
        headers=headers,
        timeout=60,
    )
    dlm_raise_for_status(response)
    return response.json()
