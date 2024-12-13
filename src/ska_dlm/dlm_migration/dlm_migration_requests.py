"""DLM Migration API module."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

import requests
from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import ska_dlm
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.exceptions import InvalidQueryParameters, ValueAlreadyInDB
from ska_dlm.fastapi_utils import decode_bearer, fastapi_auto_annotate
from ska_dlm.typer_utils import dump_short_stacktrace

from .. import CONFIG
from ..data_item import set_state, set_uri
from ..dlm_db.db_access import DB
from ..dlm_ingest import init_data_item
from ..dlm_request import query_data_item
from ..dlm_storage import check_item_on_storage, get_storage_config, query_storage
from ..exceptions import UnmetPreconditionForOperation

logger = logging.getLogger(__name__)

origins = ["http://localhost", "http://localhost:5000", "http://localhost:8004"]


def _query_job_status(job_id: str):
    request_url = f"{CONFIG.RCLONE.url}/job/status"
    post_data = {"jobid": job_id}

    logger.info("rclone request: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=1800)
    return request.json()


def _query_core_stats(job_id: str):
    request_url = f"{CONFIG.RCLONE.url}/core/stats"
    post_data = {"jobid": job_id}

    logger.info("rclone request: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=1800)
    return request.json()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Periodically wake up and query rclone for the status of all outstanding migrations."""
    # TODO: wake every X seconds (CONFIG.DLM.migration_manager.polling_interval)

    # get list of all outstanding migrations from DB
    migrations = DB.select(CONFIG.DLM.migration_table, params={"limit": 1000, "completed": False})
    logger.info("number of outstanding migrations: %s", len(migrations))

    for migration in migrations:
        # get details for this migration
        migration_id = migration["migration_id"]
        job_id = migration["job_id"]
        logger.info("migration %s: %s", migration_id, job_id)

        # query rclone for job/status
        status_json = _query_job_status(job_id)

        # query rclone for core/stats
        stats_json = _query_core_stats(job_id)

        # update migration database
        DB.update(
            CONFIG.DLM.migration_table,
            params={"job_id": job_id},
            json={"job_status": status_json, "job_stats": stats_json},
        )


rest = fastapi_auto_annotate(
    FastAPI(
        title="SKA-DLM: Migration Manager REST API",
        description="REST interface of the SKA-DLM Migration Manager",
        version=ska_dlm.__version__,
        license_info={"name": "BSD-3-Clause", "identifier": "BSD-3-Clause"},
        lifespan=lifespan,
    )
)
rest.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cli = ExceptionHandlingTyper()
cli.exception_handler(ValueAlreadyInDB)(dump_short_stacktrace)


# pylint: disable=unused-argument
@rest.exception_handler(IOError)
def ioerror_exception_handler(request: Request, exc: IOError):
    """Catch IOError and send a JSONResponse."""
    return JSONResponse(
        status_code=500,
        content={"exec": "IOError", "message": f"{str(exc)}"},
    )


def rclone_copy(src_fs: str, src_remote: str, dst_fs: str, dst_remote: str, item_type: str):
    """Copy a file from one place to another."""
    # if the item is a measurement set then use the copy directory command

    if item_type == "ms":
        request_url = f"{CONFIG.RCLONE.url}/sync/copy"
        post_data = {
            "srcFs": f"{src_fs}{src_remote}",
            "dstFs": f"{dst_fs}{dst_remote}",
            "no-check-dest": "true",
            "s3-no-check-bucket": "true",
            "_async": "true",
        }
    else:
        request_url = f"{CONFIG.RCLONE.url}/operations/copyfile"
        post_data = {
            "srcFs": src_fs,
            "srcRemote": src_remote,
            "dstFs": dst_fs,
            "dstRemote": dst_remote,
            "_async": "true",
        }

    logger.info("rclone copy request: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=1800)
    logger.info("Response status code: %s", request.status_code)
    return request.status_code, request.json()


@cli.command()
@rest.get("/migration/query_migrations")
def query_migrations() -> list:
    """
    Query for all migrations.

    Returns
    -------
    list
    """
    params = {"limit": 1000}

    return DB.select(CONFIG.DLM.migration_table, params=params)


def _create_migration_record(
    server_id, job_id, oid, source_storage_id, destination_storage_id, authorization
):
    # decode the username from the authorization
    username = None
    user_info = decode_bearer(authorization)
    if user_info:
        username = user_info.get("preferred_username", None)
        if username is None:
            raise ValueError("Username not found in profile")

    # add migration to DB
    json_data = {
        "server_id": server_id,
        "job_id": job_id,
        "oid": oid,
        "source_storage_id": source_storage_id,
        "destination_storage_id": destination_storage_id,
        "user": username,
    }
    return DB.insert(CONFIG.DLM.migration_table, json=json_data)


@cli.command()
@rest.post("/migration/copy_data_item")
def copy_data_item(
    # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    destination_name: str = "",
    destination_id: str = "",
    path: str = "",
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Copy a data_item from source to destination.

    Steps
    (1) get the current storage_id(s) of the item
    (2) convert one(first) storage_id to a configured rclone backend
    (3) check whether item already exists on destination
    (4) initialize the new item with the same OID on the new storage
    (5) use the rclone copy command to copy it to the new location
    (6) make sure the copy was successful

    Parameters
    ----------
    item_name : str
        data item name, when empty the first 1000 items are returned, by default ""
    oid : str
        object id, Return data_items referred to by the OID provided, by default ""
    uid : str
        Return data_item referred to by the UID provided, by default ""
    destination_name : str
        the name of the destination storage volume, by default ""
    destination_id : str
        the destination storage, by default ""
    path : str
        the destination path, by default ""
    authorization : str, optional
        Validated Bearer token with UserInfo

    Returns
    -------
    str
        uid: The uid of the new item copy.
        migration_id: Migration ID used to check current migration status of copy.

    Raises
    ------
    InvalidQueryParameters
        Neither an item_name, OID nor UID parameter provided.
    UnmetPreconditionForOperation
        No data item found for copying.
    """
    if not item_name and not oid and not uid:
        raise InvalidQueryParameters("Either an item_name or an OID or an UID has to be provided!")
    orig_item = query_data_item(item_name, oid, uid)
    if orig_item:
        orig_item = orig_item[0]
    else:
        raise UnmetPreconditionForOperation("No data item found for copying")
    # (1)
    item_name = orig_item["item_name"]
    storages = check_item_on_storage(item_name)
    # we pick the first data_item returned record for now
    if storages:
        storage = storages[0]
    else:
        raise UnmetPreconditionForOperation("Data item not in specified storage")
    # (2)
    s_config = get_storage_config(storage_id=storage["storage_id"])
    if not s_config:
        raise UnmetPreconditionForOperation("No configuration for source storage found!")

    s_config = s_config[0]
    source = {"backend": f"{s_config['name']}:", "path": storage["uri"]}
    if not path:
        path = storage["uri"]
    if destination_name:
        destination = query_storage(storage_name=destination_name)
        if not destination:
            raise UnmetPreconditionForOperation(
                f"Unable to get ID of destination storage: {destination_name}."
            )
        destination_id = destination[0]["storage_id"]
    d_config = get_storage_config(storage_id=destination_id)
    if not d_config:
        raise UnmetPreconditionForOperation("Unable to get configuration for destination storage!")
    d_config = d_config[0]
    dest = {"backend": f"{d_config['name']}:", "path": path}
    # (3)
    init_item = {
        "item_name": item_name,
        "oid": orig_item["oid"],
        "storage_id": destination_id,
    }
    uid = init_data_item(json_data=init_item)
    # (5)
    # TODO(yan-xxx) abstract the actual function called away to allow for different
    # mechanisms to perform the copy. Also needs to be a non-blocking call
    # scheduling a job for dlm_migration service.
    logger.info("source: %s", source)

    status_code, content = rclone_copy(
        source["backend"], source["path"], dest["backend"], dest["path"], orig_item["item_format"]
    )

    if status_code != 200:
        return IOError("rclone copy failed")

    # add row to migration table
    # NOTE: temporarily use server_id='rclone0' until we actually have multiple rclone servers
    record = _create_migration_record(
        "rclone0",
        content["jobid"],
        orig_item["oid"],
        storage["storage_id"],
        destination_id,
        authorization,
    )
    # (6)
    set_uri(uid, dest["path"], destination_id)
    # all done! Set data_item state to READY
    set_state(uid, "READY")
    return {"uid": uid, "migration_id": record[0]["migration_id"]}
