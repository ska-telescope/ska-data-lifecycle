"""DLM ingest API module."""

import logging
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

import ska_dlm
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.fastapi_utils import decode_bearer, fastapi_auto_annotate
from ska_dlm.typer_types import JsonObjectOption
from ska_dlm.typer_utils import dump_short_stacktrace

from .. import CONFIG
from ..data_item import set_metadata, set_state, set_uri
from ..dlm_db.db_access import DB
from ..dlm_request import query_data_item
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


class ItemType(str, Enum):
    """Data Item on the filesystem."""

    UNKNOWN = "unknown"
    """A single file."""
    FILE = "file"
    """A single file."""
    CONTAINER = "container"
    """A directory superset with parents."""


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
@rest.post("/ingest/init_data_item", response_model=str)
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
    item_name
        the item_name, can be empty, but then json_data has to be specified.
    phase
        the phase this item is set to (usually inherited from the storage)
    json_data
        data item table values.
    authorization
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
        post_data = {"item_name": item_name, "uid_phase": phase, "item_owner": username}
    elif json_data:
        post_data = json_data
    else:
        raise InvalidQueryParameters("Either item_name or json_data is required")
    return DB.insert(CONFIG.DLM.dlm_table, json=post_data)[0]["uid"]


@cli.command()
@rest.post("/ingest/register_data_item", response_model=str)
def register_data_item(  # noqa: C901
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    item_name: str,  # TODO: YAN-2002
    uri: str,
    item_type: ItemType = ItemType.FILE,
    storage_name: str = "",
    storage_id: str = "",
    parents: str | None = None,
    metadata: JsonObjectOption = None,
    do_storage_access_check: bool = True,
    authorization: Annotated[str | None, Header()] = None,
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
    username = None
    user_info = decode_bearer(authorization)
    if user_info:
        username = user_info.get("preferred_username", None)
        if username is None:
            raise ValueError("Username not found in profile")

    if item_type not in set(ItemType):
        raise ValueError(f"Invalid item type {item_type}")

    # (1)
    storages = query_storage(storage_name=storage_name, storage_id=storage_id)
    if not storages:
        raise UnmetPreconditionForOperation(
            f"No storages found for {storage_name=}, {storage_id=}"
        )
    storage_id = storages[0]["storage_id"]
    file_path = f"{storages[0]['root_directory']}/{uri}".replace("//", "/")

    # (2)
    if do_storage_access_check and not check_storage_access(
        storage_name=storage_name, storage_id=storage_id, remote_file_path=file_path
    ):
        raise UnmetPreconditionForOperation(
            f"""Ingested data item is not accessible using {storage_name=},
                remote_file_path={repr(file_path)}"""
        )

    # (3)
    ex_data_item = query_data_item(item_name=item_name, storage_id=storage_id)
    if ex_data_item:
        raise ValueAlreadyInDB(f"Item is already registered on storage! {item_name}")

    # (4)
    init_item = {
        "item_name": item_name,
        "storage_id": storage_id,
        "uid_phase": storages[0]["storage_phase"],
        "item_type": item_type,
        "item_owner": username,
        "parents": parents,
    }
    uid = init_data_item(json_data=init_item)

    # (5)
    set_uri(uid, uri, storage_id)

    # (6) Set data_item state to READY
    set_state(uid, "READY")

    # (7) Populate the metadata column in the database
    if metadata is None:
        logger.warning("No metadata provided. Initializing metadata with uid and item_name.")
        metadata = {}

    metadata["uid"] = uid
    metadata["item_name"] = item_name
    set_metadata(uid, metadata)

    return uid
