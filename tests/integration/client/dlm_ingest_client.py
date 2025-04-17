"""dlm_ingest REST client."""

from enum import Enum
from typing import Any, Union

import requests

from ska_dlm.typer_types import JsonObjectOption
from tests.integration.client.exception_handler import dlm_raise_for_status

INGEST_URL = ""
TOKEN: str = None

JsonType = Union[dict[str, Any], list[Any], str, int, float, bool, None]


class ItemType(str, Enum):
    """Data Item on the filesystem."""

    UNKNOWN = "unknown"
    """A single file."""
    FILE = "file"
    """A single file."""
    CONTAINER = "container"
    """A directory superset with parents."""


# pylint: disable=unused-argument
def init_data_item(item_name: str | None = None, phase: str = "GAS", json_data: str = "") -> str:
    """Initialize a new data_item.

    item_name or json_data is required.

    Parameters
    ----------
    item_name
        the item_name, can be empty, but then json_data has to be specified.
    phase
        the phase this item is set to (usually inherited from the storage)
    json_data
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
    uri: str,
    item_type: ItemType = ItemType.FILE,
    storage_name: str = "",
    storage_id: str = "",
    parents: str | None = None,
    metadata: JsonObjectOption = None,
    do_storage_access_check: bool = True,
    authorization: str | None = None,
) -> str:
    """Ingest a data_item (register function is an alias).

    This high level function is a combination of init_data_item, set_uri and set_state(READY).
    It also checks whether a data_item is already registered on the requested storage.

    (1) check whether requested storage is known and accessible
    (2) check, if required, whether item is accessible/exists on that storage
    (3) check whether item is already registered on that storage
    (4) initialize the item on the storage
    (5) set the access path to the payload
    (6) set state to READY
    (7) save metadata in the data_item table

    Parameters
    ----------
    item_name
        item name to register with. Does not need to be unique.
    uri
        the relative access path to the payload.
    item_type
        type of the data item (container, file)
    storage_name
        the name of the configured storage volume (name or ID required)
    storage_id
        the ID of the configured storage.
    parents
        uuid of parent item
    metadata
        metadata provided by the client
    do_storage_access_check
        perform check_storage_access() against provided storage and uri
    authorization
        Validated Bearer token with UserInfo

    Returns
    -------
    str
        data_item UID

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
