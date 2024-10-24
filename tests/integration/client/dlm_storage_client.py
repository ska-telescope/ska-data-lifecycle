"""dlm_storage REST client"""

import json

import requests

from ska_dlm.exceptions import (
    InvalidQueryParameters,
    UnmetPreconditionForOperation,
    ValueAlreadyInDB,
)
from ska_dlm.typer_types import JsonObjectArg

STORAGE_URL = ""
SESSION: requests.Session = None


def raise_typer_except(response: requests.Response):
    """Check for exceptional response status code and raise same exceptions
    as CLI interface."""
    if response.status_code == 422:
        text = json.loads(response.text)
        if "exec" in text:
            match text["exec"]:
                case "ValueAlreadyInDB":
                    raise ValueAlreadyInDB(text["message"])
                case "InvalidQueryParameters":
                    raise InvalidQueryParameters(text["message"])
                case "UnmetPreconditionForOperation":
                    raise UnmetPreconditionForOperation(text["message"])
    response.raise_for_status()


# pylint: disable=unused-argument
def init_location(
    location_name: str = "",
    location_type: str = "",
    location_country: str = "",
    location_city: str = "",
    location_facility: str = "",
) -> str:
    """Initialize a new location for a storage by specifying the location_name or location_id."""
    params = {k: v for k, v in locals().items() if v}
    response = SESSION.post(f"{STORAGE_URL}/storage/init_location", params=params, timeout=60)
    raise_typer_except(response)
    return response.json()


# pylint: disable=unused-argument
def init_storage(  # pylint: disable=R0913
    storage_name: str = "",  # pylint: disable=W0613
    location_name: str = "",
    location_id: str = "",
    storage_type: str = "",  # pylint: disable=W0613
    storage_interface: str = "",  # pylint: disable=W0613
    storage_capacity: int = -1,  # pylint: disable=W0613
    storage_phase_level: str = "GAS",  # pylint: disable=W0613
    json_data: str = "",
) -> str:
    """
    Intialize a new storage by at least specifying an item_name.

    Parameters
    ----------
    storage_name : str, optional
        _description_
    location_name : str, optional
        _description_
    location_id : str, optional
        _description_
    storage_type: str
        _description_
    storage_interface: str
        _description_
    storage_capacity: int
        _description_
    storage_phase_level: str
        _description_
    json_data: str
        _description_

    Returns
    -------
    Either a storage_ID or an empty string
    """
    params = {k: v for k, v in locals().items() if v}
    response = SESSION.post(f"{STORAGE_URL}/storage/init_storage", params=params, timeout=60)
    raise_typer_except(response)
    return response.json()


# pylint: disable=unused-argument
def query_location(location_name: str = "", location_id: str = "") -> list:
    """
    Query a location by at least specifying an location_name.

    Parameters
    ----------
    location_name
        could be empty, in which case the first 1000 items are returned
    location_id
        Return locations referred to by the location_id provided.

    Returns
    -------
    str
    """
    params = {k: v for k, v in locals().items() if v}
    response = SESSION.get(f"{STORAGE_URL}/storage/query_location", params=params, timeout=60)
    raise_typer_except(response)
    return response.json()


# pylint: disable=unused-argument
def create_storage_config(
    config: dict, storage_id: str = "", storage_name: str = "", config_type="rclone"
) -> str:
    """
    Create a new record in the storage_config table for a storage with the given id.

    Parameters
    ----------
    config
        the configuration entry. For rclone this is a JSON formatted string
    storage_id
        the storage_id for which to create the entry.
    storage_name
        the name of the storage for which the config is provided.
    config_type
        default is rclone, but could be something else in the future.

    Returns
    -------
    str
        the ID of the configuration entry.
    """
    params = {k: v for k, v in locals().items() if v}
    response = SESSION.post(
        f"{STORAGE_URL}/storage/create_storage_config", params=params, json=config, timeout=60
    )
    raise_typer_except(response)
    return response.json()


def rclone_config(config: JsonObjectArg) -> bool:
    """
    Create a new rclone backend configuration entry on the rclone server.

    Parameters
    ----------
    config
        a dictionary containing the configuration
    """
    response = SESSION.post(f"{STORAGE_URL}/storage/rclone_config", json=config, timeout=60)
    raise_typer_except(response)
    return bool(response.text)


# pylint: disable=unused-argument
def query_storage(storage_name: str = "", storage_id: str = "") -> list:
    """
    Query a storage by at least specifying a storage_name.

    Parameters
    ----------
    storage_name
        could be empty, in which case the first 1000 items are returned
    storage_id
        Return locations referred to by the location_id provided.

    Returns:
    --------
    list
    """
    params = {k: v for k, v in locals().items() if v}
    response = SESSION.get(f"{STORAGE_URL}/storage/query_storage", params=params, timeout=60)
    raise_typer_except(response)
    return response.json()
