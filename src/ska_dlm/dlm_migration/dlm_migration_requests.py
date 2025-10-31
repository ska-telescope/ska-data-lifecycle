"""DLM Migration API module."""

import asyncio
import logging
import random
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
from ..data_item import delete_data_item_entry, set_state
from ..dlm_db.db_access import DB
from ..dlm_ingest import init_data_item
from ..dlm_ingest.dlm_ingest_requests import ItemType
from ..dlm_request import query_data_item
from ..dlm_storage import check_item_on_storage, get_storage_config, query_storage
from ..exceptions import UnmetPreconditionForOperation

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the lowest level to log (e.g., DEBUG, INFO, WARNING, ERROR)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # Logs to the terminal (stdout)
)
logger = logging.getLogger(__name__)

origins = ["http://localhost", "http://localhost:5000", "http://localhost:8004"]


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    """Lifespan hook for startup and shutdown."""
    if len(CONFIG.RCLONE) == 0:
        raise ValueError("No Rclone URLs")

    task = asyncio.create_task(
        _poll_status_loop(
            interval=CONFIG.DLM.migration_manager.polling_interval,
        )
    )
    yield
    logger.info("shutting down")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:  # pylint: disable=broad-except
        logger.exception("Unexpected error shutting down")


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


async def _query_job_status(url: str, job_id: int):
    request_url = f"{url}/job/status"
    post_data = {"jobid": job_id}

    loop = asyncio.get_event_loop()
    logger.info("rclone request: %s, %s", request_url, post_data)
    request = await loop.run_in_executor(
        None, partial(requests.post, request_url, post_data, timeout=1800, verify=False)
    )
    return request.json()


async def _query_core_stats(url: str, group_id: str):
    request_url = f"{url}/core/stats"
    post_data = {"group": group_id}

    loop = asyncio.get_event_loop()
    logger.info("rclone request: %s, %s", request_url, post_data)
    request = await loop.run_in_executor(
        None, partial(requests.post, request_url, post_data, timeout=1800, verify=False)
    )
    return request.json()


async def _poll_status_loop(interval: int):
    """Periodically wake up and poll migration status."""
    while True:
        try:
            await update_migration_statuses()
        except asyncio.CancelledError:
            break
        except OSError:
            logger.exception("Failed to poll migration job statuses")
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error polling migration job statuses")
        await asyncio.sleep(interval)


# pylint: disable=unused-argument
@rest.exception_handler(IOError)
def ioerror_exception_handler(request: Request, exc: IOError):
    """Catch IOError and send a JSONResponse."""
    return JSONResponse(
        status_code=500,
        content={"exec": "IOError", "message": f"{str(exc)}"},
    )


def rclone_copy(
    url: str,
    src_fs: str,
    src_remote: str,
    src_root_dir: str,
    dst_fs: str,
    dst_remote: str,
    dest_root_dir: str,
    item_type: str,
    # pylint: disable=too-many-arguments,too-many-positional-arguments
):
    """Copy a file from one place to another."""
    # if the item is a measurement set then use the copy directory command

    dest_abs_path = f"{dest_root_dir}/{dst_remote}".replace("//", "/")
    if item_type == ItemType.CONTAINER:
        request_url = f"{url}/sync/copy"
        post_data = {
            "srcFs": f"{src_fs}{src_root_dir}/{src_remote}",
            "dstFs": f"{dest_abs_path}",
            "no-check-dest": "true",
            "s3-no-check-bucket": "true",
            "_async": "true",
        }
    else:
        request_url = f"{url}/operations/copyfile"
        post_data = {
            "srcFs": f"{src_fs}{src_root_dir}",
            "srcRemote": src_remote,
            "dstFs": dst_fs,
            "dstRemote": dst_remote,
            "_async": "true",
        }

    logger.info("rclone copy request: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=1800, verify=False)
    logger.info("Response status code: %s", request.status_code)
    return request.status_code, request.json()


async def update_migration_statuses():
    """
    Update the migration job status in the database for all pending rclone jobs.

    This is performed by querying the rclone service instances.

    Raises
    ------
    IOError
        Error contacting database or rclone services.
    """
    loop = asyncio.get_event_loop()

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
        # Want to try block so we go through each migration record to the end of the list
        try:
            # get details for this migration
            migration_id = migration["migration_id"]
            job_id = migration["job_id"]
            url = migration["url"]
            logger.info("migration %s: %s", migration_id, job_id)

            stats_json = ""
            complete = False
            # query rclone for job/status
            status_json = await _query_job_status(url, job_id)
            if status_json["finished"] is False:
                continue

            if not status_json["error"]:
                # query rclone for core/stats
                stats_json = await _query_core_stats(url, status_json["group"])
                complete = status_json["success"]
            else:
                # if job is in error we dont want to query it again so mark it complete
                complete = True

            # Get record for remote data item
            source_data_item = query_data_item(
                oid=migration["oid"], storage_id=migration["destination_storage_id"]
            )
            if source_data_item:
                if status_json["success"] is True:
                    set_state(uid=source_data_item[0]["uid"], state="READY")
                else:
                    # delete remote data item if there is a transfer problem
                    delete_data_item_entry(uid=source_data_item[0]["uid"])

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
        except Exception as e:  # pylint: disable=broad-except
            logging.exception(e)


@cli.command()
@rest.get("/migration/query_migrations", response_model=list[dict])
def query_migrations(
    authorization: Annotated[str | None, Header()] = None,
    start_date: str | None = None,
    end_date: str | None = None,
    storage_id: str | None = None,
) -> list[dict]:
    """
    Query for all migrations by a given user, with optional filters.

    Parameters
    ----------
    authorization
        Validated Bearer token with UserInfo
    start_date
        Filter migrations that started after this date (YYYY-MM-DD or YYYYMMDD)
    end_date
        Filter migrations that ended before this date (YYYY-MM-DD or YYYYMMDD)
    storage_id
        Filter migrations by a specific storage location

    Returns
    -------
    list[dict]
    """
    # decode the username from the authorization
    username = None
    user_info = decode_bearer(authorization)
    if user_info:
        username = user_info.get("preferred_username", None)
        if username is None:
            raise ValueError("Username not found in profile")

    params = {"limit": 1000, "user": f"eq.{username}"}

    date_filters = []
    if start_date:
        date_filters.append(f"gte.{start_date}")

    if end_date:
        date_filters.append(f"lte.{end_date}")

    if date_filters:
        if start_date and end_date:
            params["and"] = f"(date.gte.{start_date},date.lte.{end_date})"  # join conditions
        elif start_date:
            params["date"] = f"gte.{start_date}"
        elif end_date:
            params["date"] = f"lte.{end_date}"

    if storage_id:
        params[
            "or"
        ] = f"(source_storage_id.eq.{storage_id},destination_storage_id.eq.{storage_id})"

    return DB.select(CONFIG.DLM.migration_table, params=params)


@cli.command()
@rest.get("/migration/get_migration")
def get_migration_record(migration_id: int) -> list[dict]:
    """
    Query for a specific migration.

    Parameters
    ----------
    migration_id
        Migration id of migration

    Returns
    -------
    list[dict]
    """
    return _get_migration_record(migration_id)


def _get_migration_record(migration_id: int) -> list[dict]:
    """
    Query for a specific migration.

    Parameters
    ----------
    migration_id
        Migration id of migration

    Returns
    -------
    list[dict]
    """
    params = {"migration_id": f"eq.{migration_id}"}
    return DB.select(CONFIG.DLM.migration_table, params=params)


def _create_migration_record(
    job_id,
    oid,
    url,
    source_storage_id,
    destination_storage_id,
    authorization,
    # pylint: disable=too-many-arguments,too-many-positional-arguments
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
        "url": url,
        "source_storage_id": source_storage_id,
        "destination_storage_id": destination_storage_id,
        "user": username,
    }
    return DB.insert(CONFIG.DLM.migration_table, json=json_data)


@cli.command()
@rest.post("/migration/copy_data_item", response_model=dict)
def copy_data_item(  # noqa: C901
    # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments,too-many-branches,too-many-statements
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    destination_name: str = "",
    destination_id: str = "",
    path: str = "",
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Copy a data_item from source to destination.

    Steps
    (1) get the current storage_id(s) of the item
    (2) convert one (first) storage_id to a configured rclone backend
    (3) initialise the new item with the same OID on the new storage
    (4) use the rclone copy command to copy it to the new location

    Parameters
    ----------
    item_name
        data item name, when empty the first 1000 items are returned, by default ""
    oid
        object id, Return data_items referred to by the OID provided, by default ""
    uid
        Return data_item referred to by the UID provided, by default ""
    destination_name
        the name of the destination storage volume, by default ""
    destination_id
        the destination storage, by default ""
    path
        the destination path relative to storage root, by default ""
    authorization
        Validated Bearer token with UserInfo

    Returns
    -------
    dict
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
        raise InvalidQueryParameters("Either item_name or OID or UID has to be provided!")
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
    source_root_path = s_config.get("root_path", "")
    source = {"backend": f"{s_config['name']}:{source_root_path}", "path": storage["uri"]}
    if not path:
        path = storage["uri"]

    destination = None
    if destination_name:
        destination = query_storage(storage_name=destination_name)
    elif destination_id:
        destination = query_storage(storage_id=destination_id)

    if not destination:
        raise UnmetPreconditionForOperation(
            f"Unable to get ID of destination storage: {destination_name}."
        )
    destination_id = destination[0]["storage_id"]

    d_config = get_storage_config(storage_id=destination_id)
    if not d_config:
        raise UnmetPreconditionForOperation("Unable to get configuration for destination storage!")
    d_config = d_config[0]
    dest_root_path = s_config.get("root_path", "")
    dest = {"backend": f"{d_config['name']}:{dest_root_path}", "path": path}

    source_storage = query_storage(storage_id=storage["storage_id"])
    if not source_storage:
        raise UnmetPreconditionForOperation(
            f"Unable to get source storage: {storage['storage_id']}."
        )

    # (3)
    init_item = {
        "item_name": item_name,
        "oid": orig_item["oid"],
        "storage_id": destination_id,
        "item_type": orig_item["item_type"],
        "metadata": orig_item["metadata"],
        "uri": path,
    }

    # Initalising with default INITIALISED
    new_item_uid = init_data_item(json_data=init_item)

    try:
        # (4)
        # TODO(yan-xxx) abstract the actual function called away to allow for different
        # mechanisms to perform the copy. Also needs to be a non-blocking call
        # scheduling a job for dlm_migration service.
        logger.info("source: %s", source)

        # get random Rclone instance to deal with copy
        url = random.choice(CONFIG.RCLONE)

        status_code, content = rclone_copy(
            url,
            source["backend"],
            source["path"],
            source_storage[0]["root_directory"],
            dest["backend"],
            dest["path"],
            destination[0]["root_directory"],
            orig_item["item_type"],
        )

        if status_code != 200:
            logger.error(
                "rclone_copy failed with status_code: %s, content: %s", status_code, content
            )
            raise OSError("rclone copy request failed.")

        # add row to migration table
        # NOTE: temporarily use server_id='rclone0' until we actually have multiple rclone servers
        record = _create_migration_record(
            content["jobid"],
            orig_item["oid"],
            url,
            source_storage[0]["storage_id"],
            destination_id,
            authorization,
        )

        return {"uid": new_item_uid, "migration_id": record[0]["migration_id"]}
    except Exception:
        # if there is any error, delete data item and raise exception
        delete_data_item_entry(uid=new_item_uid)
        raise
