"""DLM ingest API module."""

import logging
from typing import Annotated

import requests
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from ska_sdp_dataproduct_metadata import MetaData

import ska_dlm
from ska_dlm.dlm_storage.dlm_storage_requests import rclone_access
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.fastapi_utils import decode_bearer, fastapi_auto_annotate
from ska_dlm.typer_types import JsonObjectOption
from ska_dlm.typer_utils import dump_short_stacktrace

from .. import CONFIG
from ..data_item import set_metadata, set_state, set_uri
from ..dlm_db.db_access import DB
from ..dlm_request import query_data_item, query_exists
from ..dlm_storage import check_storage_access, query_storage
from ..exceptions import InvalidQueryParameters, UnmetPreconditionForOperation, ValueAlreadyInDB

logger = logging.getLogger(__name__)

rest = fastapi_auto_annotate(
    FastAPI(
        title="SKA-DLM: Ingest Manager REST API",
        description="REST interface of the SKA-DLM Ingest Manager",
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


cli = ExceptionHandlingTyper()
cli.exception_handler(ValueAlreadyInDB)(dump_short_stacktrace)


@cli.command()
@rest.post("/ingest/init_data_item")
def init_data_item(
    item_name: str | None = None,
    phase: str = "GAS",
    json_data: JsonObjectOption = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Initialize a new data_item.

    item_name or json_data is required.

    Parameters
    ----------
    item_name : str
        the item_name, can be empty, but then json_data has to be specified.
    phase : str, optional
        the phase this item is set to (usually inherited from the storage)
    json_data : dict | None, optional
        data item table values.
    authorization : str, optional
        Validated Bearer token with UserInfo

    Returns
    -------
    str
        created data_item UID

    Raises
    ------
    InvalidQueryParameters
    """
    username = None
    user_info = decode_bearer(authorization)
    if user_info:
        username = user_info.get("preferred_username", None)
        if username is None:
            raise ValueError("Username not found in profile")

    if item_name:
        post_data = {"item_name": item_name, "item_phase": phase, "item_owner": username}
    elif json_data:
        post_data = json_data
    else:
        raise InvalidQueryParameters("Either item_name or json_data is required")
    return DB.insert(CONFIG.DLM.dlm_table, json=post_data)[0]["uid"]


@cli.command()
@rest.post("/ingest/register_data_item")
def register_data_item(  # noqa: C901
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    item_name: str,
    uri: str = "",
    storage_name: str = "",
    storage_id: str = "",
    metadata: JsonObjectOption = None,
    item_format: str | None = "unknown",
    eb_id: str | None = None,
    authorization: Annotated[str | None, Header()] = None,
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
    uri: str
        the access path to the payload.
    storage_name: str
        the name of the configured storage volume (name or ID required)
    storage_id: str, optional
        the ID of the configured storage.
    metadata: dict, optional
        metadata provided by the client
    item_format: str, optional
        format of the data item
    eb_id: str | None, optional
        execution block ID provided by the client
    authorization: str
        Validated Bearer token with UserInfo

    Returns
    -------
    str
        data_item UID

    Raises
    ------
    UnmetPreconditionForOperation
    """
    username = None
    user_info = decode_bearer(authorization)
    if user_info:
        username = user_info.get("preferred_username", None)
        if username is None:
            raise ValueError("Username not found in profile")

    # (1)
    storages = query_storage(storage_name=storage_name, storage_id=storage_id)
    if not storages:
        raise UnmetPreconditionForOperation(
            f"No storages found for {storage_name=}, {storage_id=}"
        )
    storage_id = storages[0]["storage_id"]
    if not check_storage_access(storage_name=storage_name, storage_id=storage_id):
        raise UnmetPreconditionForOperation(
            f"Requested storage volume is not accessible by DLM! {storage_name}"
        )
    # (2)
    if not rclone_access(storage_name, uri):  # TODO: don't call into rclone directly
        raise UnmetPreconditionForOperation(f"File {uri} does not exist on {storage_name}")
    if query_exists(item_name):
        ex_storage_id = query_data_item(item_name)[0]["storage_id"]
        if storage_id == ex_storage_id:
            raise ValueAlreadyInDB(f"Item is already registered on storage! {item_name=}")
    # (3)
    init_item = {
        "item_name": item_name,
        "storage_id": storage_id,
        "item_phase": storages[0]["storage_phase_level"],
        "item_format": item_format,
        "item_owner": username,
    }
    uid = init_data_item(json_data=init_item)

    # (4)
    set_uri(uid, uri, storage_id)

    # (5) Set data_item state to READY
    set_state(uid, "READY")

    # (6) Populate the metadata column in the database
    if metadata is None:
        logger.warning("No metadata provided. Initializing metadata with uid and item_name.")
        metadata = {}

    metadata["uid"] = uid
    metadata["item_name"] = item_name
    set_metadata(uid, metadata)

    # (7)
    notify_data_dashboard(metadata)  # TODO: the DPD call is currently broken

    return uid


def notify_data_dashboard(metadata: dict | MetaData) -> None:
    """HTTP POST MetaData json object to the Data Product Dashboard."""
    headers = {"Content-Type": "application/json"}
    url = CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata"

    if isinstance(metadata, MetaData):
        metadata = metadata.get_data()

    # Validation
    payload = None
    try:
        if not isinstance(metadata, dict) or "execution_block" not in metadata:
            raise TypeError(
                f"metadata must contain an 'execution_block', got {type(metadata)} {metadata}"
            )
        payload = metadata
    except (TypeError, ValueError) as err:
        logger.error("Failed to parse metadata: %s. Not notifying dashboard.", err)

    if payload is not None:
        try:
            resp = requests.request("POST", url, headers=headers, data=payload, timeout=2)
            resp.raise_for_status()
            logger.info(
                "POSTed metadata (execution_block: %s) to %s", metadata["execution_block"], url
            )
        except requests.RequestException as err:
            logger.exception("POST error notifying dataproduct dashboard at: %s - %s", url, err)
