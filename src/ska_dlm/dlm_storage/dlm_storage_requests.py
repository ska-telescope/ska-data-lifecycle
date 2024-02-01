"""Wrap the most important postgREST API calls."""
import inspect
import json
import logging

import requests

from .. import CONFIG

logger = logging.getLogger(__name__)


def args_dict(func):
    """Get arguments of function inside the function. Used as decorator."""

    def wrapper(*args, **kwargs):
        bound_args = inspect.signature(func).bind(*args, **kwargs)
        bound_args.apply_defaults()
        logger.info(dict(bound_args.arguments))
        kwargs.update({"args": dict(bound_args.arguments)})
        logger.info("Added args: %s", kwargs)
        return func(*args, **kwargs)

    return wrapper


def query_location(location_name: str = "", location_id: str = "", query_string: str = "") -> list:
    """
    Query a location by at least specifying an location_name.

    Parameters:
    -----------
    location_name: could be empty, in which case the first 1000 items are returned
    location_id:    Return locations referred to by the location_id provided.
    query_string, an arbitrary postgREST query string

    Returns:
    --------
    str
    """
    api_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.location_table}?limit=1000"
    if location_name or location_id:
        if location_name:
            request_url = f"{api_url}&location_name=eq.{location_name}"
        elif location_id:
            request_url = f"{api_url}&location_id=eq.{location_id}"
    elif query_string:
        request_url = f"{api_url}&{query_string}"
    else:
        request_url = f"{api_url}"
    request = requests.get(request_url, timeout=10)
    if request.status_code == 200:
        return request.json()
    logger.info("Response status code: %s", request.status_code)
    return []


@args_dict
def init_storage(  # pylint: disable=R0913, R0914
    storage_name: str = "",  # pylint: disable=W0613
    location_name: str = "",
    location_id: str = "",
    storage_type: str = "",  # pylint: disable=W0613
    storage_interface: str = "",  # pylint: disable=W0613
    storage_capacity: int = -1,  # pylint: disable=W0613
    json_data: str = "",
    **kwargs,
) -> str:
    """
    Intialize a new storage by at least specifying an item_name.

    Parameters:
    -----------
    storage_name

    Returns:
    --------
    Either a storage_ID or an empty string
    """
    request_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.storage_table}?limit=1000"
    complete = True
    mandatory_keys = [
        "storage_name",
        "location_id",
        "storage_type",
        "storage_interface",
        "storage_capacity",
    ]
    post_data = {}
    if json_data:
        json_dict = json.loads(json_data)
        for k in mandatory_keys:
            if k not in json_dict:
                logger.error("Parameter %s is required in json_data!", k)
                return ""
        post_data = json_data
    else:
        provided_args = kwargs["args"]
        if location_name and not location_id:
            result = query_location(location_name)
            if result:
                location_id = result[0]["location_id"]
        for k in mandatory_keys:
            if k in provided_args:
                post_data.update({k: provided_args[k]})
            else:
                logger.error("Argument %s is mandatory!", k)
                complete = True
    if complete:
        request = requests.post(
            request_url,
            json=post_data,
            headers={"Prefer": "missing=default, return=representation"},
            timeout=10,
        )
        if request.status_code in [200, 201]:
            return request.json()[0]["storage_id"]
        logger.info("Status code: %s", request.status_code)
        logger.info("%s", request.json())
    return ""


def create_storage_config(storage_id: str, config: str, config_type="rclone") -> str:
    """
    Create a new record in the storage_config table for a storage with the given id.

    Parameters:
    -----------
    storage_id: the storage_id for which to create the entry.
    config: the configuration entry. For rclone this is s JSON formatted string
    config_type: default is rclone, but could be something else in the future.

    Returns:
    --------
    str, the ID of the config entry or empty string
    """
    api_url = f"{CONFIG.REST.base_url}/storage_config"
    request_url = f"{api_url}"
    post_data = {"storage_id": storage_id, "config": config, "config_type": config_type}
    request = requests.post(
        request_url,
        json=post_data,
        headers={"Prefer": "missing=default, return=representation"},
        timeout=10,
    )
    if request.status_code == 201:
        return request.json()[0]["config_id"]
    logger.info("Response status code: %s", request.status_code)
    return ""


def init_location(
    location_name: str = "",
    location_type: str = "",
    location_country: str = "",
    location_city: str = "",
    location_facility: str = "",
) -> str:
    """Initialize a new location for a stroage by specifying the location_name or location_id."""
    request_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.location_table}?limit=1000"
    res = query_location(location_name)
    if len(res) != 0:
        logger.warning("A location with this name exists already: %s", location_name)
        return ""
    # if json_data:
    #     post_data = json_data
    if location_name and location_type:
        post_data = {"location_name": location_name, "location_type": location_type}
        if location_country:
            post_data.update({"location_country": location_country})
        if location_city:
            post_data.update({"location_city": location_city})
        if location_facility:
            post_data.update({"location_facility": location_facility})
    else:
        logger.error("Location name is required if not specifying json_data!")
        return ""
    request = requests.post(
        request_url,
        json=post_data,
        headers={"Prefer": "missing=default, return=representation"},
        timeout=10,
    )
    if request.status_code not in [200, 201]:
        logger.error("Status code %s", request.status_code)
        return ""
    return request.json()[0]["location_id"]


def query_storage(storage_name: str = "", storage_id: str = "", query_string: str = "") -> list:
    """
    Query a storage by at least specifying a storage_name.

    Parameters:
    -----------
    storage_name: could be empty, in which case the first 1000 items are returned
    stoage_id:    Return locations referred to by the location_id provided.
    query_string, an arbitrary postgREST query string

    Returns:
    --------
    str
    """
    api_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.storage_table}?limit=1000"
    if storage_name or storage_id:
        if storage_name:
            request_url = f"{api_url}&storage_name=eq.{storage_name}"
        elif storage_id:
            request_url = f"{api_url}&storage_id=eq.{storage_id}"
    elif query_string:
        request_url = f"{api_url}&{query_string}"
    else:
        request_url = f"{api_url}"
    request = requests.get(request_url, timeout=10)
    if request.status_code == 200:
        return request.json()
    logger.info("Response status code: %s", request.status_code)
    return []
