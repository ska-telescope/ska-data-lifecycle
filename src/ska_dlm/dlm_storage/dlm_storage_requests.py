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
    Query a new data_item by at least specifying an item_name.

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
            request_url = f"{api_url}&item_name=eq.{location_name}"
        elif location_id:
            request_url = f"{api_url}&oid=eq.{location_id}"
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


def init_location(
    location_name: str = "",
    location_country: str = "",
    location_city: str = "",
    location_facility: str = "",
    json_data: str = "",
) -> str:
    """Initialize a new location for a stroage by specifying the location_name or location_id."""
    request_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.location_table}?limit=1000"
    res = query_location(location_name)
    if len(res) != 0:
        logger.warning("A location with this name exists already: %s", location_name)
        return ""
    if json_data:
        post_data = json_data
    elif location_name:
        post_data = {"location_name": location_name}
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
    return request.json()[0]["location_id"]


# def set_state(uid: str, state):
#     """ """
#     pass


# def set_oid_expiration(oid: str, expiration: str):
#     """ """
#     pass


# def set_uid_expiration(uid: str, expiration: str):
#     """ """
#     pass


# def set_user(oid: str = "", uid: str = "", user: str = "SKA"):
#     """ """
#     pass


# def set_group(oid: str = "", uid: str = "", group: str = "SKA"):
#     """ """
#     pass


# def set_acl(oid: str = "", uid: str = "", acl: str = "{}") -> uid:
#     """ """
#     pass
