"""DLM Migration API module."""

import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
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


async def _query_job_status(job_id: int):
    request_url = f"{CONFIG.RCLONE.url}/job/status"
    post_data = {"jobid": job_id}

    loop = asyncio.get_event_loop()
    logger.info("rclone request: %s, %s", request_url, post_data)
    request = await loop.run_in_executor(
        None, partial(requests.post, request_url, post_data, timeout=1800)
    )
    return request.json()


async def _query_core_stats(group_id: str):
    request_url = f"{CONFIG.RCLONE.url}/core/stats"
    post_data = {"group": group_id}

    loop = asyncio.get_event_loop()
    logger.info("rclone request: %s, %s", request_url, post_data)
    request = await loop.run_in_executor(
        None, partial(requests.post, request_url, post_data, timeout=1800)
    )
    return request.json()


async def _poll_status_loop(interval: int, running: asyncio.Event):
    """Periodically wake up and poll migration status."""
    while running.is_set() is False:
        await update_migration_statuses()
        await asyncio.sleep(interval)


@asynccontextmanager
async def app_lifespan(_):
    """Lifepsan hook for startup and shutdown."""
    running = asyncio.Event()
    task = asyncio.create_task(
        _poll_status_loop(interval=CONFIG.DLM.migration_manager.polling_interval, running=running)
    )
    yield
    running.set()
    await task
    logger.info("shutting down")


rest = fastapi_auto_annotate(
    FastAPI(
        title="SKA-DLM: Migration Manager REST API",
        description="REST interface of the SKA-DLM Migration Manager",
        version=ska_dlm.__version__,
        license_info={"name": "BSD-3-Clause", "identifier": "BSD-3-Clause"},
        lifespan=app_lifespan,
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


async def update_migration_statuses():
    """
    Update the migration job status in the database for all pending rclone jobs.

    This is performed by querying the rclone service instances.
    """
    loop = asyncio.get_event_loop()

    try:
        # get list of all outstanding migrations from DB
        migrations = await loop.run_in_executor(
            None,
            partial(
                DB.select,
                CONFIG.DLM.migration_table,
                params={"complete": "eq.false"},
            ),
        )

        logger.info("number of outstanding migrations: %s", len(migrations))

        for migration in migrations:
            # get details for this migration
            migration_id = migration["migration_id"]
            job_id = migration["job_id"]
            logger.info("migration %s: %s", migration_id, job_id)

            stats_json = ""
            complete = False
            # query rclone for job/status
            status_json = await _query_job_status(job_id)
            if not status_json["error"]:
                # query rclone for core/stats
                stats_json = await _query_core_stats(status_json["group"])
                complete = status_json["success"]
            else:
                # if job is in error we dont want to query it again so mark it complete
                complete = True

            # update migration database
            DB.update(
                CONFIG.DLM.migration_table,
                params={"migration_id": f"eq.{migration['migration_id']}"},
                json={
                    "job_status": status_json,
                    "job_stats": stats_json,
                    "complete": complete,
                },
            )
    except IOError:
        logger.exception("Failed to poll migration job statuses")
    except Exception:  # pylint: disable=broad-except
        logging.exception("Unexpected error")


@cli.command()
@rest.get("/migration/query_migrations")
def query_migrations(
    authorization: Annotated[str | None, Header()] = None,
) -> list:
    """
    Query for all migrations by a given user.

    Parameters
    ----------
    authorization : str, optional
        Validated Bearer token with UserInfo

    Returns
    -------
    list
    """
    # decode the username from the authorization
    username = None
    user_info = decode_bearer(authorization)
    if user_info:
        username = user_info.get("preferred_username", None)
        if username is None:
            raise ValueError("Username not found in profile")

    params = {"limit": 1000, "user": f"eq.{username}"}

    return DB.select(CONFIG.DLM.migration_table, params=params)


def _create_migration_record(
    job_id, oid, source_storage_id, destination_storage_id, authorization
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
