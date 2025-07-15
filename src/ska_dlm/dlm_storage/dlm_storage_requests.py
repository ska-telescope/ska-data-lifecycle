"""DLM Storage API module."""

import logging
import random

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import ska_dlm
from ska_dlm.dlm_db.db_access import DB
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.fastapi_utils import fastapi_auto_annotate
from ska_dlm.typer_types import JsonObjectArg, JsonObjectOption

from .. import CONFIG
from ..data_item import set_state
from ..dlm_request import query_expired, query_item_storage
from ..exceptions import InvalidQueryParameters, UnmetPreconditionForOperation, ValueAlreadyInDB

logger = logging.getLogger(__name__)

cli = ExceptionHandlingTyper()
rest = fastapi_auto_annotate(
    FastAPI(
        title="SKA-DLM: Storage Manager REST API",
        description="REST interface of the SKA-DLM Storage Manager",
        version=ska_dlm.__version__,
        license_info={"name": "BSD-3-Clause", "identifier": "BSD-3-Clause"},
    )
)


# pylint: disable=unused-argument
@rest.exception_handler(ValueAlreadyInDB)
def valuealreadyindb_exception_handler(request: Request, exc: ValueAlreadyInDB):
    """Catch ValueAlreadyInDB and send a JSONResponse."""
    return JSONResponse(
        status_code=422,
        content={"exec": "ValueAlreadyInDB", "message": f"{str(exc)}"},
    )


# pylint: disable=unused-argument
@rest.exception_handler(UnmetPreconditionForOperation)
def unmetprecondition_exception_handler(request: Request, exc: UnmetPreconditionForOperation):
    """Catch UnmetPreconditionForOperation and send a JSONResponse."""
    return JSONResponse(
        status_code=422,
        content={"exec": "UnmetPreconditionForOperation", "message": f"{str(exc)}"},
    )


# pylint: disable=unused-argument
@rest.exception_handler(InvalidQueryParameters)
def invalidquery_exception_handler(request: Request, exc: InvalidQueryParameters):
    """Catch InvalidQueryParameters and send a JSONResponse."""
    return JSONResponse(
        status_code=422,
        content={"exec": "InvalidQueryParameters", "message": f"{str(exc)}"},
    )


@cli.command()
@rest.get("/storage/query_location", response_model=list[dict])
def query_location(location_name: str = "", location_id: str = "") -> list[dict]:
    """
    Query a location.

    Parameters
    ----------
    location_name
        could be empty, in which case the first 1000 items are returned
    location_id
        Return locations referred to by the location_id provided.

    Returns
    -------
    list[dict]
    """
    params = {"limit": 1000}
    if location_name or location_id:
        if location_name:
            params["location_name"] = f"eq.{location_name}"
        elif location_id:
            params["location_id"] = f"eq.{location_id}"
    return DB.select(CONFIG.DLM.location_table, params=params)


@cli.command()
@rest.post("/storage/init_storage", response_model=str)
# pylint: disable=too-many-arguments,unused-argument,too-many-positional-arguments
def init_storage(
    storage_name: str,
    storage_type: str,
    storage_interface: str,
    root_directory: str,
    location_id: str | None = None,
    location_name: str | None = None,
    storage_capacity: int = -1,
    storage_phase: str = "GAS",
    rclone_config: JsonObjectOption = None,
) -> str:
    """
    Initialise a new storage.

    Parameters
    ----------
    storage_name
        An organisation or owner name for the storage.
    storage_type
        high level type of the storage: 'filesystem', 'objectstore' or 'tape'
    storage_interface
        storage interface for rclone access, e.g. "posix", "s3"
    root_directory
        data directory as an absolute path on the remote storage endpoint
    location_id
        a dlm registered location id
    location_name
        a dlm registered location name
    storage_capacity
        reserved storage capacity in bytes
    storage_phase
        one of "GAS", "LIQUID", "SOLID"
    rclone_config
        extra rclone values such as secrets required for connection

    Returns
    -------
    str
        Either a storage_ID or an empty string
    """
    provided_args = dict(locals())
    mandatory_keys = [
        "storage_name",
        "storage_type",
        "storage_interface",
        "location_id",
        "storage_capacity",
        "storage_phase",
        "root_directory",
    ]
    # TODO remove keys none values
    post_data = {}
    if rclone_config:
        json_dict = rclone_config
        for k in mandatory_keys:
            if k not in json_dict:
                logger.error("Parameter %s is required in json_data!", k)
                return ""
        post_data = json_dict
    else:
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


@cli.command()
@rest.post("/storage/create_storage_config", response_model=str)
def create_storage_config(
    config: JsonObjectArg,
    storage_id: str = "",
    storage_name: str = "",
    config_type: str = "rclone",
) -> str:
    """Create a new record in the storage_config table for a given storage_id.

    Parameters
    ----------
    config
        the configuration entry. For rclone this is a JSON formatted string
    storage_id
        the storage_id for which to create the entry.
    storage_name
        the name of the storage for which the config is provided.
    config_type
        default is 'rclone'. Alternative enums from ConfigType.

    Returns
    -------
    str
        the ID of the configuration entry.

    Raises
    ------
    UnmetPreconditionForOperation
        Neither storage_id nor storage_name is specified.
    """
    if not storage_name and not storage_id:
        raise UnmetPreconditionForOperation("Neither storage_id nor storage_name is specified.")
    if storage_name:
        storage_id = query_storage(storage_name=storage_name)[0]["storage_id"]
    post_data = {
        "storage_id": storage_id,
        "config": config,
        "config_type": config_type,
    }
    if create_rclone_config(config):
        return DB.insert(CONFIG.DLM.storage_config_table, json=post_data)[0]["config_id"]
    raise UnmetPreconditionForOperation("Configuring rclone server failed!")


@cli.command()
@rest.get("/storage/get_storage_config", response_model=list[dict])
def get_storage_config(
    storage_id: str = "", storage_name: str = "", config_type: str = "rclone"
) -> list[dict]:
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
    list[dict]
        list of configs as json

    Raises
    ------
    UnmetPreconditionForOperation
        storage_name does not exist in database
    """
    params = {}
    if not storage_name and not storage_id:
        # raise UnmetPreconditionForOperation("Either storage_name or storage_id is required.")
        params = {"limit": 1000}
    elif storage_name:
        storage = query_storage(storage_name=storage_name)
        if storage:
            storage_id = storage[0]["storage_id"]
        else:
            raise UnmetPreconditionForOperation(f"Can't get storage_id for {storage_name}")
    if not params:
        params = {
            "limit": 1000,
            "storage_id": f"eq.{storage_id}",
            "config_type": f"eq.{config_type}",
        }
    result = DB.select(CONFIG.DLM.storage_config_table, params=params)
    return [entry["config"] for entry in result] if result else []


@cli.command()
@rest.post("/storage/rclone_config", response_model=bool)
def create_rclone_config(config: JsonObjectArg) -> bool:
    """Create a new rclone backend configuration entry on the rclone server.

    Parameters
    ----------
    config
        a json string containing the configuration

    Returns
    -------
    bool
        True if configuration is successful
    """
    for url in CONFIG.RCLONE:
        request_url = f"{url}/config/create"
        logger.info("Creating new rclone config: %s %s", request_url, config)
        request = requests.post(
            request_url,
            json=config,
            headers={"Content-type": "application/json"},
            timeout=10,
            verify=False,
        )
        logger.info("Response status code: %s", request.status_code)
        if request.status_code != 200:
            return False
    return True


def check_storage_access(
    storage_name: str = "", storage_id: str = "", remote_file_path: str = ""
) -> bool:
    """Check whether storage is accessible.

    Parameters
    ----------
    storage_name
        The name of the storage volume (either name or ID are required)
    storage_id
        The ID of the storage volume.
    remote_file_path
        Remote file.

    Returns
    -------
    bool
        True is accessible
    """
    storages = query_storage(storage_name=storage_name, storage_id=storage_id)
    if not storages:
        logger.error("The requested storage is unknown: %s [%s]", storage_name, storage_id)
        return False
    storage_id = storages[0]["storage_id"]
    storage_name = storages[0]["storage_name"]
    config = get_storage_config(
        storage_id=storage_id, storage_name=storage_name, config_type="rclone"
    )
    if not config:
        raise UnmetPreconditionForOperation(
            "No valid configuration for storage found!", storage_name
        )
    volume_name = config[0]["name"]
    return rclone_access(volume_name, remote_file_path)


def rclone_access(volume: str, remote_file_path: str = "", config: dict | None = None) -> bool:
    """Check whether a configured backend is accessible.

    Parameters
    ----------
    volume
        Volume name
    remote_file_path
        Remote file path, by default ""
    config
        override rclone config values, by default None

    Returns
    -------
    bool
        True if access is allowed.
    """
    url = random.choice(CONFIG.RCLONE)
    request_url = f"{url}/operations/stat"
    if config:
        post_data = config
    else:
        volume_name = f"{volume}:" if volume[-1] != ":" else volume
        post_data = {
            "fs": volume_name,
            "remote": remote_file_path,
        }
    logger.info("rclone access check: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=10, verify=False)
    if request.status_code != 200 or not request.json()["item"]:
        logger.warning("rclone does not have access: %s, %s", request.status_code, request.json())
        return False
    return True


def rclone_delete(volume: str, fpath: str) -> bool:
    """Delete a file, referred to by fpath from a volume using rclone.

    Parameters
    ----------
    volume
        the configured volume name hosting <fpath>.
    fpath
        the file path.

    Returns
    -------
    bool
        True if successful
    """
    volume_name = f"{volume}:" if volume[-1] != ":" else volume
    if not rclone_access(volume_name, fpath):
        logger.error("Can't access %s on %s!", fpath, volume_name)
        return False
    url = random.choice(CONFIG.RCLONE)
    request_url = f"{url}/operations/deletefile"
    post_data = {
        "fs": volume_name,
        "remote": fpath,
    }
    logger.info("rclone deletion: %s, %s", request_url, post_data)
    request = requests.post(request_url, data=post_data, timeout=10, verify=False)
    if request.status_code != 200:
        logger.info("Error response status code: %s", request.status_code)
        return False
    return True


@cli.command()
@rest.post("/storage/init_location", response_model=str)
def init_location(
    location_name: str,
    location_type: str,
    location_country: str = "",
    location_city: str = "",
    location_facility: str = "",
) -> str:
    """Initialise a new storage location.

    Parameters
    ----------
    location_name
        the orgization or owner's name managing the storage location.
    location_type
        the location type, e.g. "low-operational"
    location_country
        the location country name (AU, ZA or UK)
    location_city
        the location city name
    location_facility
        the location facility name

    Returns
    -------
    str
        created location_id

    Raises
    ------
    InvalidQueryParameters
        either location_name or location_type is empty
    ValueAlreadyInDB
        location_name aleady exists in database
    """
    if not (location_name and location_type):
        raise InvalidQueryParameters("location_name and location_type cannot be empty")
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


@cli.command()
@rest.get("/storage/query_storage", response_model=list[dict])
def query_storage(storage_name: str = "", storage_id: str = "") -> list[dict]:
    """
    Query storage locations.

    Parameters
    ----------
    storage_name
        Name of the storage to query. If not provided, the first 1000 locations are returned.
    storage_id
        ID of the storage to query. Ignored if storage_name is provided.

    Returns
    -------
    list[dict]
        A list of storage locations matching the query criteria.
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
    """Check whether item is on storage.

    Parameters
    ----------
    item_name
        could be empty, in which case the first 1000 items are returned
    oid
        Return data_items referred to by the OID provided.
    uid
        Return data_item referred to by the UID provided.
    storage_name
        the name of the storage device
    storage_id
        the storage_id of a destination storage

    Returns
    -------
    bool
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
    """Delete the payload of a data_item referred to by the provided UID.

    Parameters
    ----------
    uid
        The UID of the data_item whose payload should be deleted.

    Returns
    -------
    bool
        True if successful
    """
    storages = query_item_storage(uid=uid)
    logger.info("Storage for this uid: %s", storages)
    if not storages:
        logger.error("Unable to identify a storage volume for this UID: %s", uid)
        return False
    if len(storages) > 1:
        logger.error("More than one storage volume keeping this UID: %s", uid)
    storage = storages[0]
    config = get_storage_config(storage["storage_id"])[0]
    volume_name = config["name"]
    if not rclone_access(volume_name):
        return False
    source_storage = query_storage(storage_id=storage["storage_id"])
    if not source_storage:
        raise UnmetPreconditionForOperation(
            f"Unable to get source storage: {storage['storage_id']}."
        )
    delete_path = f"{source_storage[0]['root_directory']}/{storage['uri']}".replace("//", "/")
    if not rclone_delete(volume_name, delete_path):
        logger.warning("rclone unable to delete data item payload: %s", uid)
        return False
    set_state(uid, "DELETED")
    logger.info("Deleted %s from %s", uid, volume_name)
    return True


def delete_uids():
    """Check for expired data items and trigger deletion."""
    expired_data_items = query_expired()

    if len(expired_data_items) > 0:
        logger.info("Found %s expired data items", len(expired_data_items))

    for data_item in expired_data_items:
        uid = data_item["uid"]

        success = delete_data_item_payload(uid)

        if not success:
            logger.warning("Unable to delete data item payload: %s", uid)


def check_storage_capacity():
    """Check remaining capacity of all storage items."""
    storage_items = query_storage()

    for storage_item in storage_items:
        if (
            storage_item["storage_use_pct"]
            >= CONFIG.DLM.storage_manager.storage_warning_percentage
        ):
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
