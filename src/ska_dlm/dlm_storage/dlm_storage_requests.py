"""Wrap the most important postgREST API calls."""

import inspect
import json
import logging

import requests

from ska_dlm.dlm_db.db_access import DB

from .. import CONFIG
from ..data_item import set_state
from ..dlm_request import query_expired, query_item_storage
from ..exceptions import InvalidQueryParameters, UnmetPreconditionForOperation, ValueAlreadyInDB

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


def query_location(location_name: str = "", location_id: str = "") -> list:
    """
    Query a location by at least specifying an location_name.

    Parameters:
    -----------
    location_name: could be empty, in which case the first 1000 items are returned
    location_id:    Return locations referred to by the location_id provided.

    Returns:
    --------
    str
    """
    params = {"limit": 1000}
    if location_name or location_id:
        if location_name:
            params["location_name"] = f"eq.{location_name}"
        elif location_id:
            params["location_id"] = f"eq.{location_id}"
    return DB.select(CONFIG.DLM.location_table, params=params)


@args_dict
def init_storage(  # pylint: disable=R0913
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
                provided_args["location_id"] = result[0]["location_id"]
        for k in mandatory_keys:
            if k in provided_args:
                post_data.update({k: provided_args[k]})
            else:
                raise InvalidQueryParameters(f"Argument {k} is mandatory!")
    return DB.insert(CONFIG.DLM.storage_table, json=post_data)[0]["storage_id"]


def create_storage_config(storage_name:str = "", storage_id: str="", config: str="", config_type="rclone") -> str:
    """
    Create a new record in the storage_config table for a storage with the given id.

    Parameters:
    -----------
    storage_name: the name of the storage for which the config is provided.
    storage_id: the storage_id for which to create the entry.
    config: the configuration entry. For rclone this is s JSON formatted string
    config_type: default is rclone, but could be something else in the future.

    Returns:
    --------
    str, the ID of the configuration entry.
    """
    if not storage_name and not storage_id:
        raise UnmetPreconditionForOperation
    if storage_name:
        storage_id = query_storage(storage_name=storage_name)[0]["storage_id"]
    post_data = {"storage_id": storage_id, "config": config, "config_type": config_type}
    return DB.insert(CONFIG.DLM.storage_config_table, json=post_data)[0]["config_id"]


def get_storage_config(storage_name:str="",storage_id: str="", config_type="rclone") -> str:
    """
    Get the storage configuration entry for a particular storage backend.

    Parameters:
    -----------
    storage_name: the name of the storage volume
    storage_id: required
    config_type: required, query only the specified type

    Returns:
    --------
    json object
    """
    params = {}
    if not storage_name and not storage_id:
        # raise UnmetPreconditionForOperation("Either storage_name or storage_id is required.")
        params = {"limit": 1000}
    elif storage_name:
        storage_id = query_storage(storage_name=storage_name)[0]["storage_id"]
    if not params: params = {
        "limit": 1000,
        "storage_id": f"eq.{storage_id}",
        "config_type": f"eq.{config_type}",
    }
    return json.loads(DB.select(CONFIG.DLM.storage_config_table, params=params)[0]["config"])


def rclone_config(config: str) -> bool:
    """
    Create a new rclone backend configuration entry on the rclone server.

    Parameters:
    -----------
    config: a json string containing the configuration
    """
    request_url = f"{CONFIG.RCLONE.url}/config/create"
    post_data = config
    logger.info("Creating new rclone config: %s %s", request_url, config)
    request = requests.post(
        request_url, post_data, headers={"Content-type": "application/json"}, timeout=10
    )
    logger.info("Response status code: %s", request.status_code)
    return request.status_code == 200


def check_storage_access(storage_name: str = "", storage_id: str = "") -> bool:
    """
    Check whether storage is accessible.

    Parameters:
    -----------
    storage_name: The name of the storage volume (either name or ID are required)
    storage_id: The ID of the storage volume.

    Returns:
    --------
    True is accessible
    """
    storages = query_storage(storage_name=storage_name, storage_id=storage_id)
    if not storages:
        logger.error("The requested storage is unknown: %s [%s]", storage_name, storage_id)
        return False
    storage_id = storages[0]["storage_id"]
    storage_name = storages[0]["storage_name"]
    config = get_storage_config(storage_id=storage_id, config_type="rclone")
    if not config:
        logger.error("No valid configuration for storage found! %s", storage_name)
        return False
    rclone_fs = config["name"]
    return rclone_access(rclone_fs)


def rclone_access(
    volume: str = "", remote: str = "", config: str = ""  # pylint disable C0103
) -> bool:
    """
    Check whether a configured backend is accessible.

    NOTE: This assumes a rclone server is running.
    """
    request_url = f"{CONFIG.RCLONE.url}/operations/stat"
    if config:
        post_data = {}
    else:
        volume = f"{volume}:" if volume[-1] != ":" else volume
        post_data = {
            "fs": volume,
            "remote": remote,
        }
    logger.info("rclone access check: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=10)
    if request.status_code != 200 or not request.json()["item"]:
        logger.info("rclone does not have access: %s, %s", request.status_code, request.json())
        return False
    return True


def rclone_delete(volume: str, fpath: str) -> bool:
    """
    Delete a file, referred to by fpath from a volume using rclone.

    Parameters:
    -----------
    volume: the configured volume name hosting <fpath>.
    fpath: the file path.

    Returns:
    bool, True if successful
    """
    volume = f"{volume}:" if volume[-1] != ":" else volume
    if not rclone_access(volume, fpath):
        logger.error("Can't access %s on %s!", fpath, volume)
        return False
    request_url = f"{CONFIG.RCLONE.url}/operations/deletefile"
    post_data = {
        "fs": volume,
        "remote": fpath,
    }
    logger.info("rclone deletion: %s, %s", request_url, post_data)
    request = requests.post(request_url, data=post_data, timeout=10)
    if request.status_code != 200:
        logger.info("Error response status code: %s", request.status_code)
        return False
    return True


def init_location(
    location_name: str = "",
    location_type: str = "",
    location_country: str = "",
    location_city: str = "",
    location_facility: str = "",
) -> str:
    """Initialize a new location for a stroage by specifying the location_name or location_id."""
    if not (location_name and location_type):
        raise InvalidQueryParameters("Location_name and location_type must be given")
    if query_location(location_name):
        raise ValueAlreadyInDB(f"A location with this name exists already: {location_name}")
    post_data = {"location_name": location_name, "location_type": location_type}
    if location_country:
        post_data["location_country"] = location_country
    if location_city:
        post_data["location_city"] = location_city
    if location_facility:
        post_data["location_facility"] = location_facility
    return DB.insert(CONFIG.DLM.location_table, json=post_data)[0]["location_id"]


def query_storage(storage_name: str = "", storage_id: str = "") -> list:
    """
    Query a storage by at least specifying a storage_name.

    Parameters:
    -----------
    storage_name: could be empty, in which case the first 1000 items are returned
    stoage_id:    Return locations referred to by the location_id provided.

    Returns:
    --------
    str
    """
    params = {"limit": 1000}
    if storage_name:
        params["storage_name"] = f"eq.{storage_name}"
    elif storage_id:
        params["storage_id"] = f"eq.{storage_id}"
    return DB.select(CONFIG.DLM.storage_table, params=params)


def check_item_on_storage(
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    storage_name: str = "",
    storage_id: str = "",
) -> bool:
    """
    Check whether item is on storage.

    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    oid:    Return data_items referred to by the OID provided.
    uid:    Return data_item referred to by the UID provided.
    storage_name: optional, the name of the storage device
    storage_id: optional, the storage_id of a destination storage
    """
    storages = query_item_storage(item_name, oid, uid)
    if not storages:
        logger.error("Unable to identify a storage volume for this data_item!")
        return []
    # additional check if a storage_name or id is provided
    for storage in storages:
        if (storage_name and storage["storage_name"] == storage_name) or (
            storage_id and storage["storage_id"] == storage_id
        ):
            logger.error("data_item '%s' already exists on destination storage!", item_name)
            return []
    return storages


def delete_data_item_payload(uid: str) -> bool:
    """
    Delete the payload of a data_item referred to by the provided UID.

    Parameters:
    -----------
    uid: The UID of the data_item whose payload should be deleted.

    Returns:
    bool, True if successful
    """
    storages = query_item_storage(uid=uid)
    logger.info("Storage for this uid: %s", storages)
    if not storages:
        logger.error("Unable to identify a storage volume for this UID: %s", uid)
        return False
    if len(storages) > 1:
        logger.error("More than one storage volume keeping this UID: %s", uid)
    storage = storages[0]
    config = get_storage_config(storage["storage_id"])
    storage_name = config["name"]
    if not rclone_access(storage_name):
        return False
    if not rclone_delete(storage_name, storage["item_name"]):
        return False
    # TODO: Need to set the state to DELETED, but that causes cyclic imports.
    if not set_state(uid, "DELETED"):
        return False
    return True


def delete_uids():
    """Check for expired data items and trigger deletion."""
    expired_data_items = query_expired()
    print(str(expired_data_items))

    if len(expired_data_items) > 0:
        logger.info("Found %s expired data items", len(expired_data_items))

    for data_item in expired_data_items:
        uid = data_item["uid"]
        print("uid " + uid)

        success = delete_data_item_payload(uid)

        if not success:
            logger.warning("Unable to delete data item payload: %s", uid)


def check_storage_capacity():
    """Check remaining capacity of all storage items."""
    storage_items = query_storage()

    for storage_item in storage_items:
        if storage_item["storage_use_pct"] >= CONFIG.DLM.STORAGE_WARNING_PERCENTAGE:
            logger.warning(
                "storage_item %s nearing full capacity (%s)",
                storage_item["storage_name"],
                storage_item["storage_use_pct"],
            )


def perform_phase_transitions():
    """Check for OIDs with insufficient phase, and trigger a phase transition."""
    required_phase_transitions = []  # dlm_storage.query_phase_transitions()

    for oid in required_phase_transitions:
        logger.warning("Incomplete implementation: phase transition required for oid: %s", oid)
