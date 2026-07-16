"""DLM Migration API module."""

import asyncio
import logging
import os
import random
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from typing import Annotated

import requests
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from requests import Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import ska_dlm
from ska_dlm.dlm_outbox.outbox import add_outbox_event
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.exceptions import InvalidQueryParameters, ValueAlreadyInDB
from ska_dlm.fastapi_utils import decode_bearer, fastapi_auto_annotate
from ska_dlm.typer_utils import dump_short_stacktrace

from .. import CONFIG
from ..data_item import delete_data_item_entry, set_state
from ..dlm_db import Migration
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

MIGRATION_DATABASE_URL = os.getenv(
    "DLM_MIGRATION_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://ska_dlm_admin:password@dlm_db:5432/ska_dlm"),
)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Lifespan hook for startup and shutdown."""
    if len(CONFIG.RCLONE) == 0:
        raise ValueError("No Rclone URLs")

    migration_engine = create_async_engine(
        MIGRATION_DATABASE_URL,
        future=True,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    migration_session_factory = sessionmaker(
        bind=migration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        future=True,
    )
    app.state.async_engine = migration_engine
    app.state.async_session_factory = migration_session_factory

    task = asyncio.create_task(
        _poll_status_loop(
            interval=CONFIG.DLM.migration_manager.polling_interval,
            async_session_factory=migration_session_factory,
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
    await migration_engine.dispose()


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


def _parse_date_filter(value: str) -> datetime:
    """Parse optional date filter values into a datetime object."""
    if len(value) == 8 and value.isdigit():
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return datetime.fromisoformat(value)


def _serialize_value(val):
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_serialize_value(v) for v in val]
    return val


def _migration_to_dict(migration: Migration) -> dict:
    """Convert a SQLAlchemy Migration model into a plain dictionary with JSON-safe values."""
    return {
        column.name: _serialize_value(getattr(migration, column.name))
        for column in migration.__table__.columns
    }


def _open_migration_session() -> AsyncSession:
    """Open a new async SQLAlchemy session from the FastAPI app state."""
    if rest.state.async_session_factory is None:  # type: ignore[attr-defined]
        raise RuntimeError("Migration session factory is not initialized")
    return rest.state.async_session_factory()  # type: ignore[attr-defined]


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


async def _poll_status_loop(interval: int, async_session_factory: sessionmaker):
    """Periodically wake up and poll migration status."""
    while True:
        try:
            async with async_session_factory() as session:
                await _update_migration_statuses(session)
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
            "dstFs": f"{dst_fs}{dest_abs_path}",
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
            "dstRemote": dest_abs_path,
            "s3-no-check-bucket": "true",
            "_async": "true",
        }

    command = f"{request_url} {str(post_data)}"

    logger.info("rclone command: %s", command)
    request = requests.post(request_url, post_data, timeout=1800, verify=False)
    logger.info("Response status code: %s", request.status_code)
    return request.status_code, request.json(), command


async def _update_migration_statuses(session: AsyncSession):
    """
    Update the migration job status in the database for all pending rclone jobs.

    This is performed by querying the rclone service instances.

    Parameters
    ----------
    session : AsyncSession
        Async SQLAlchemy session used for the update.

    Raises
    ------
    IOError
        Error contacting database or rclone services.
    """
    result = await session.execute(select(Migration).where(Migration.complete.is_(False)))
    migrations = result.scalars().all()

    if len(migrations) > 0:
        logger.info("number of outstanding migrations: %s", len(migrations))

    for migration in migrations:
        # Want to try block so we go through each migration record to the end of the list
        try:
            # get details for this migration
            migration_id = migration.migration_id
            job_id = migration.job_id
            url = migration.url
            logger.info("migration %s: %s", migration_id, job_id)

            migration_complete = False
            # query rclone for job/status
            status_json = await _query_job_status(url, job_id)
            stats_json = await _query_core_stats(url, status_json["group"])

            if status_json["finished"] is True:
                migration_complete = True
                # Get record for remote data item
                dest_data_item = query_data_item(
                    oid=migration.oid, storage_id=migration.destination_storage_id
                )

                if dest_data_item:
                    if status_json["success"] is True:
                        logging.info(
                            "Migration %s success, data item %s",
                            migration_id,
                            dest_data_item[0]["uid"],
                        )
                        set_state(uid=dest_data_item[0]["uid"], state="READY")
                    else:
                        # delete remote data item if there is a transfer problem
                        logging.info(
                            "Migration %s failed, deleting data item %s",
                            migration_id,
                            dest_data_item[0]["uid"],
                        )
                        delete_data_item_entry(uid=dest_data_item[0]["uid"])

            stmt = (
                update(Migration)
                .where(Migration.migration_id == migration_id)
                .values(
                    job_status=status_json,
                    job_stats=stats_json,
                    complete=migration_complete,
                    completion_date=func.now(),  # pylint: disable=not-callable
                )
                .returning(Migration)
            )
            migration_obj = await session.scalar(stmt)

            await add_outbox_event(
                session=session,
                event_type="dlm.migration.update",
                payload=_migration_to_dict(migration_obj),
            )

            await session.commit()
        except Exception as e:  # pylint: disable=broad-except
            logging.exception(e)


@cli.command()
@rest.get("/migration/query_migrations", response_model=list[dict])
async def query_migrations(
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

    stmt = select(Migration)
    if username:
        stmt = stmt.where(Migration.user == username)

    if start_date:
        stmt = stmt.where(Migration.date >= _parse_date_filter(start_date))
    if end_date:
        stmt = stmt.where(Migration.completion_date <= _parse_date_filter(end_date))

    if storage_id:
        stmt = stmt.where(
            or_(
                Migration.source_storage_id == storage_id,
                Migration.destination_storage_id == storage_id,
            )
        )

    async with _open_migration_session() as session:
        result = await session.execute(stmt)
        migrations = result.scalars().all()
    return [_migration_to_dict(item) for item in migrations]


@cli.command()
@rest.get("/migration/get_migration", response_model=list[dict])
async def get_migration_record(migration_id: int) -> list[dict]:
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
    async with _open_migration_session() as session:
        return await _get_migration_record(migration_id, session)


async def _get_migration_record(migration_id: int, session: AsyncSession) -> list[dict]:
    """
    Query for a specific migration.

    Parameters
    ----------
    migration_id : int
        Migration id of migration
    session : AsyncSession
        Async SQLAlchemy session used for the update.

    Returns
    -------
    list[dict]
    """
    stmt = select(Migration).where(Migration.migration_id == migration_id)
    result = await session.execute(stmt)
    migrations = result.scalars().all()
    return [_migration_to_dict(item) for item in migrations]


async def _create_migration_record(
    session: AsyncSession,
    job_id,
    oid,
    url,
    source_storage_id,
    destination_storage_id,
    authorization,
    command,
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
    record = Migration(
        job_id=job_id,
        oid=oid,
        url=url,
        source_storage_id=source_storage_id,
        destination_storage_id=destination_storage_id,
        user=username,
        command=command,
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    await session.commit()
    return _migration_to_dict(record)


@cli.command()
@rest.post("/migration/copy_data_item", response_model=dict)
async def copy_data_item(  # noqa: C901
    # pylint: disable=too-many-arguments,too-many-positional-arguments
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
    (5) add record to the migration table

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
    async with _open_migration_session() as session:
        return await _copy_data_item(
            session=session,
            item_name=item_name,
            oid=oid,
            uid=uid,
            destination_name=destination_name,
            destination_id=destination_id,
            path=path,
            authorization=authorization,
        )


async def _copy_data_item(  # noqa: C901
    # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments,too-many-branches,too-many-statements
    session: AsyncSession,
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    destination_name: str = "",
    destination_id: str = "",
    path: str = "",
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Copy a data_item from source to destination."""
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
    source_root_path = s_config.get("root_path", "/")
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
    dest_id = destination[0]["storage_id"]
    dest_phase = destination[0]["storage_phase"]

    d_config = get_storage_config(storage_id=dest_id)
    if not d_config:
        raise UnmetPreconditionForOperation("Unable to get configuration for destination storage!")
    d_config = d_config[0]
    dest_root_path = d_config.get("root_path", "/")
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
        "storage_id": dest_id,
        "item_type": orig_item["item_type"],
        "target_phase": orig_item["target_phase"],
        "uid_expiration": orig_item["uid_expiration"],
        "oid_expiration": orig_item["oid_expiration"],
        "uid_phase": dest_phase,
        "metadata": orig_item["metadata"],
        "uri": path,
    }

    # Initalising with default INITIALISED
    new_item_uid = init_data_item(json_data=init_item)

    try:
        # (4) copy item to the new location
        # TODO(yan-xxx) abstract the actual function called away to allow for different
        # mechanisms to perform the copy. Also needs to be a non-blocking call
        # scheduling a job for dlm_migration service.
        logger.info("source: %s", source)
        logger.info("destination: %s", dest)

        # get random Rclone instance to deal with copy
        url = random.choice(CONFIG.RCLONE)

        status_code, content, command = rclone_copy(
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

        # (5) add row to migration table
        # NOTE: temporarily use server_id='rclone0' until we actually have multiple rclone servers
        record = await _create_migration_record(
            session,
            content["jobid"],
            orig_item["oid"],
            url,
            source_storage[0]["storage_id"],
            dest_id,
            authorization,
            command,
        )
        session.commit()

        return {"uid": new_item_uid, "migration_id": record["migration_id"]}
    except Exception:
        # if there is any error, delete data item and raise exception
        delete_data_item_entry(uid=new_item_uid)
        raise
