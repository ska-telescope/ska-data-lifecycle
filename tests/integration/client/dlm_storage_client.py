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


def dlm_raise_for_status(response: requests.Response):
    """Raises a DLM exception for error response status codes."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response.status_code == 422:  # Unprocessable Content
            try:
                obj = json.loads(response.text)
            except json.JSONDecodeError as dexc:
                raise dexc from exc
            if "exec" in obj:
                match obj["exec"]:
                    case "ValueAlreadyInDB":
                        raise ValueAlreadyInDB(obj["message"]) from exc
                    case "InvalidQueryParameters":
                        raise InvalidQueryParameters(obj["message"]) from exc
                    case "UnmetPreconditionForOperation":
                        raise UnmetPreconditionForOperation(obj["message"]) from exc
        raise


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
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument,too-many-arguments,too-many-positional-arguments
def init_storage(
    storage_name: str = "",
    location_name: str = "",
    location_id: str = "",
    storage_type: str = "",
    storage_interface: str = "",
    storage_capacity: int = -1,
    storage_phase_level: str = "GAS",
    json_data: dict | None = None,
) -> str:
    """
    Intialize a new storage by at least specifying a storage_name.

    Parameters
    ----------
    storage_name : str
        An organisation or owner name for the storage.
    storage_type: str
        high level type of the storage, e.g. "disk", "s3"
    storage_interface: str
        storage interface for rclone access, e.g. "posix", "s3"
    location_name : str, optional
        a dlm registered location name
    location_id : str, optional
        a dlm registered location id
    storage_capacity: int, optional
        reserved storage capacity in bytes
    storage_phase_level: str, optional
        one of "GAS", "LIQUID", "SOLID"
    json_data: dict, optional
        extra rclone values such as secrets required for connection

    Returns
    -------
    str
        Either a storage_ID or an empty string
    """
    params = {k: v for k, v in locals().items() if v}
    response = SESSION.post(f"{STORAGE_URL}/storage/init_storage", params=params, json=json_data, timeout=60)
    dlm_raise_for_status(response)
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
    dlm_raise_for_status(response)
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
    dlm_raise_for_status(response)
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
    dlm_raise_for_status(response)
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
    dlm_raise_for_status(response)
    return response.json()
