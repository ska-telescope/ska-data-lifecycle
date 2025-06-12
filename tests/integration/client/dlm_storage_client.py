"""dlm_storage REST client."""

import requests

from ska_dlm.typer_types import JsonObjectArg
from tests.integration.client.exception_handler import dlm_raise_for_status

STORAGE_URL = ""
TOKEN: str = None


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
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{STORAGE_URL}/storage/init_location", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument,too-many-arguments,too-many-positional-arguments
def init_storage(
    storage_name: str = "",
    location_name: str = "",
    storage_interface: str = "",
    root_directory: str = "",
    location_id: str = "",
    storage_type: str = "",
    storage_capacity: int = -1,
    storage_phase: str = "GAS",
    json_data: dict | None = None,
) -> str:
    """
    Initialize a new storage.

    location_name or location_id is required.

    Parameters
    ----------
    storage_name
        An organisation or owner name for the storage.
    location_name
        a dlm registered location name
    storage_interface
        storage interface for rclone access, e.g. "posix", "s3"
    root_directory
        root directory of storage
    location_id
        a dlm registered location id
    storage_type
        high level type of the storage, e.g. "disk", "s3"
    storage_capacity
        reserved storage capacity in bytes
    storage_phase
        one of "GAS", "LIQUID", "SOLID"
    json_data
        extra rclone values such as secrets required for connection

    Returns
    -------
    str
        Either a storage_ID or an empty string
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{STORAGE_URL}/storage/init_storage",
        params=params,
        json=json_data,
        headers=headers,
        timeout=60,
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument
def query_location(location_name: str = "", location_id: str = "") -> list:
    """
    Query a location.

    location_name or location_id is required.

    Parameters
    ----------
    location_name
        could be empty, in which case the first 1000 items are returned
    location_id
        Return locations referred to by the location_id provided.

    Returns
    -------
    list
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{STORAGE_URL}/storage/query_location", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


# pylint: disable=unused-argument
def create_storage_config(
    config: dict, storage_id: str = "", storage_name: str = "", config_type: str = "rclone"
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
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{STORAGE_URL}/storage/create_storage_config",
        params=params,
        json=config,
        headers=headers,
        timeout=60,
    )
    dlm_raise_for_status(response)
    return response.json()


def create_rclone_config(config: JsonObjectArg) -> bool:
    """
    Create a new rclone backend configuration entry on the rclone server.

    Parameters
    ----------
    config
        a dictionary containing the configuration

    Returns
    -------
    bool
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{STORAGE_URL}/storage/rclone_config", json=config, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return bool(response.text)


# pylint: disable=unused-argument
def query_storage(storage_name: str = "", storage_id: str = "") -> list[dict]:
    """
    Query a storage.

    storage_name or storage_id is required.

    Parameters
    ----------
    storage_name
        could be empty, in which case the first 1000 items are returned
    storage_id
        Return locations referred to by the location_id provided.

    Returns
    -------
    list[dict]
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{STORAGE_URL}/storage/query_storage", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()


def get_storage_config(
    storage_id: str = "", storage_name: str = "", config_type: str = "rclone"
) -> list[str]:
    """Get the storage configuration entry for a particular storage backend.

    Parameters
    ----------
    storage_id
        the storage id, by default ""
    storage_name
        the name of the storage volume, by default ""
    config_type
        query only the specified type, by default "rclone"

    Returns
    -------
    list[str]
        list of json configs

    Raises
    ------
    UnmetPreconditionForOperation
        storage_name does not exist in database
    """
    params = {k: v for k, v in locals().items() if v}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(
        f"{STORAGE_URL}/storage/get_storage_config", params=params, headers=headers, timeout=60
    )
    dlm_raise_for_status(response)
    return response.json()
