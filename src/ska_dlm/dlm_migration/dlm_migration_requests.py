# pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
"""DLM Migration API module."""

import logging
import os
import posixpath
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from requests import Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import aliased, sessionmaker

import ska_dlm
from ska_dlm.common_types import ConfigType, ItemState
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.exceptions import (
    DatabaseOperationError,
    InvalidQueryParameters,
    UnmetPreconditionForOperation,
    ValueAlreadyInDB,
)
from ska_dlm.fastapi_utils import decode_bearer, fastapi_auto_annotate
from ska_dlm.typer_types import JsonObjectOption
from ska_dlm.typer_utils import dump_short_stacktrace

from ..dlm_db import DataItem, Migration, Storage, StorageConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the lowest level to log (e.g., DEBUG, INFO, WARNING, ERROR)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # Logs to the terminal (stdout)
)
logger = logging.getLogger(__name__)

origins = [
    "http://localhost",
    "http://localhost:5000",
    "http://localhost:8004",
    "http://dlm_migration.localhost",
]

MIGRATION_DATABASE_URL = os.getenv(
    "DLM_MIGRATION_DATABASE_URL",
    os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://ska_dlm_admin:password@dlm_db:5432/ska_dlm_testing"
    ),
)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Lifespan hook for startup and shutdown."""
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
    yield
    logger.info("shutting down")
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
        attr.columns[0].name: _serialize_value(getattr(migration, attr.key))
        for attr in migration.__mapper__.column_attrs
    }


def _storage_remote_path(root_directory: str, remote_path: str) -> str:
    """Resolve a storage-relative path beneath its configured root directory."""
    return posixpath.normpath(posixpath.join(root_directory or "/", remote_path.lstrip("/")))


def _destination_paths_overlap(left: str, right: str, root_directory: str) -> bool:
    """Detect identical or nested destination paths on one storage."""
    left_path = _storage_remote_path(root_directory, left)
    right_path = _storage_remote_path(root_directory, right)
    return posixpath.commonpath((left_path, right_path)) in (left_path, right_path)


def _open_migration_session() -> AsyncSession:
    """Open a new async SQLAlchemy session from the FastAPI app state."""
    if rest.state.async_session_factory is None:  # type: ignore[attr-defined]
        raise RuntimeError("Migration session factory is not initialized")
    return rest.state.async_session_factory()  # type: ignore[attr-defined]


# pylint: disable=unused-argument
@rest.exception_handler(IOError)
def ioerror_exception_handler(request: Request, exc: IOError):
    """Catch IOError and send a JSONResponse."""
    return JSONResponse(
        status_code=500,
        content={"exec": "IOError", "message": f"{str(exc)}"},
    )


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

    source_storage = aliased(Storage)
    destination_storage = aliased(Storage)
    stmt = (
        select(
            Migration,
            source_storage.storage_name.label("source_storage_name"),
            destination_storage.storage_name.label("destination_storage_name"),
            DataItem.item_name.label("item_name"),
        )
        .join(source_storage, Migration.source_storage_id == source_storage.storage_id)
        .join(
            destination_storage,
            Migration.destination_storage_id == destination_storage.storage_id,
        )
        .outerjoin(DataItem, DataItem.UID == Migration.uid)
    )
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
        migrations = result.all()
    return [
        {
            **_migration_to_dict(migration),
            "source_storage_name": source_storage_name,
            "destination_storage_name": destination_storage_name,
            "item_name": item_name,
        }
        for migration, source_storage_name, destination_storage_name, item_name in migrations
    ]


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


@cli.command()
@rest.post("/migration/copy_data_item", response_model=dict)
async def copy_data_item(  # noqa: C901
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    destination_name: str = "",
    destination_id: str = "",
    path: str = "",
    authorization: Annotated[str | None, Header()] = None,
    metadata: JsonObjectOption = None,
    origin: str | None = None,
) -> dict:
    """Copy a data_item from source to destination.

    Steps
    (1) lock the source data item and resolve its source/destination storage configuration
    (2) create a pending migration while preventing concurrent copies of the source item
    (3) return the destination UID and migration ID for asynchronous tracking

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
    metadata
        Metadata associated with the migration. Can be Null.
    origin
        The service that triggered the migration request. Expected values are: configdb-watcher,
        directory-watcher, heuristics and cli.

    Returns
    -------
    dict
        uid: The uid reserved for the new item copy.
        migration_id: Migration ID used to check current migration status of copy.

    Raises
    ------
    InvalidQueryParameters
        Neither an item_name, OID nor UID parameter provided.
    UnmetPreconditionForOperation
        No data item found for copying.
    """
    try:
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
                migration_metadata=metadata,
                origin=origin,
            )
    except InvalidQueryParameters as exc:
        raise HTTPException(
            status_code=409,
            detail={"exec": "InvalidQueryParameters", "message": str(exc)},
        ) from exc
    except UnmetPreconditionForOperation as exc:
        raise HTTPException(
            status_code=409,
            detail={"exec": "UnmetPreconditionForOperation", "message": str(exc)},
        ) from exc
    except ValueAlreadyInDB as exc:
        raise HTTPException(
            status_code=409,
            detail={"exec": "ValueAlreadyInDB", "message": str(exc)},
        ) from exc
    except DatabaseOperationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"exec": "DatabaseOperationError", "message": str(exc)},
        ) from exc
    except (IOError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail={"exec": "IOError", "message": str(exc)},
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Unexpected error while copying a data item")
        raise HTTPException(
            status_code=500,
            detail={"exec": type(exc).__name__, "message": str(exc)},
        ) from exc


async def _copy_data_item(  # noqa: C901
    session: AsyncSession,
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    destination_name: str = "",
    destination_id: str = "",
    path: str = "",
    authorization: Annotated[str | None, Header()] = None,
    migration_metadata: JsonObjectOption = None,
    origin: str | None = None,
) -> dict:
    """Create a queued migration for a data item."""
    if not item_name and not oid and not uid:
        raise InvalidQueryParameters("Either item_name or OID or UID has to be provided!")
    if not destination_name and not destination_id:
        raise UnmetPreconditionForOperation("A destination storage name or ID is required.")

    source_filter = (
        DataItem.UID == uuid.UUID(uid)
        if uid
        else DataItem.OID == uuid.UUID(oid)
        if oid
        else DataItem.item_name == item_name
    )
    username = None
    user_info = decode_bearer(authorization)
    if user_info:
        username = user_info.get("preferred_username")
        if username is None:
            raise ValueError("Username not found in profile")

    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    async with transaction:
        source_item = await session.scalar(
            select(DataItem)
            .where(source_filter)
            .order_by(DataItem.UID_creation, DataItem.UID)
            .limit(1)
            .with_for_update()
        )
        if source_item is None:
            raise UnmetPreconditionForOperation("No data item found for copying")
        active_migration_id = await session.scalar(
            select(Migration.migration_id)
            .where(
                Migration.uid == source_item.UID,
                Migration.complete.is_(False),
            )
            .limit(1)
        )
        if active_migration_id is not None:
            raise UnmetPreconditionForOperation("Data item already has an active migration")
        if source_item.storage_id is None:
            raise UnmetPreconditionForOperation("Data item is not associated with a storage")

        source_storage = aliased(Storage)
        destination_storage = aliased(Storage)
        source_config = aliased(StorageConfig)
        destination_config = aliased(StorageConfig)
        destination_filter = (
            destination_storage.storage_name == destination_name
            if destination_name
            else destination_storage.storage_id == uuid.UUID(destination_id)
        )
        storage_stmt = (
            select(source_storage, source_config, destination_storage, destination_config)
            .join(source_config, source_config.storage_id == source_storage.storage_id)
            .join(
                destination_storage,
                destination_filter,
            )
            .join(
                destination_config,
                destination_config.storage_id == destination_storage.storage_id,
            )
            .where(source_storage.storage_id == source_item.storage_id)
            .where(source_config.config_type == ConfigType.RCLONE)
            .where(destination_config.config_type == ConfigType.RCLONE)
            .order_by(source_config.config_date, destination_config.config_date)
            .limit(1)
        )
        storage_result = (await session.execute(storage_stmt)).first()
        if storage_result is None:
            raise UnmetPreconditionForOperation(
                "Unable to resolve source/destination storage and Rclone configuration"
            )
        (
            source_storage_row,
            source_config_row,
            destination_storage_row,
            destination_config_row,
        ) = storage_result

        destination_path = path or source_item.uri
        if not destination_path:
            raise UnmetPreconditionForOperation("Data item has no URI to copy")
        lock_key = int.from_bytes(destination_storage_row.storage_id.bytes[:8], "big", signed=True)
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))
        reserved_paths = (
            await session.scalars(
                select(Migration.destination_path).where(
                    Migration.destination_storage_id == destination_storage_row.storage_id,
                    Migration.complete.is_(False),
                )
            )
        ).all()
        if any(
            not reserved_path
            or _destination_paths_overlap(
                destination_path, reserved_path, destination_storage_row.root_directory or "/"
            )
            for reserved_path in reserved_paths
        ):
            raise UnmetPreconditionForOperation(
                "Destination path overlaps an active migration or an unknown legacy destination"
            )
        destination_uid = uuid.uuid4()
        migration = Migration(
            uid=source_item.UID,
            destination_uid=destination_uid,
            destination_path=destination_path,
            source_storage_id=source_storage_row.storage_id,
            destination_storage_id=destination_storage_row.storage_id,
            user=username or "SKA",
            command=None,
            migration_metadata=migration_metadata,
            origin=origin,
        )
        destination_values = {
            attribute.key: getattr(source_item, attribute.key)
            for attribute in DataItem.__mapper__.column_attrs
            if attribute.key not in {"UID", "UID_creation", "UID_deletion"}
        }
        destination_values.update(
            UID=destination_uid,
            UID_deletion=None,
            storage_id=destination_storage_row.storage_id,
            UID_phase=destination_storage_row.storage_phase,
            item_state=ItemState.INITIALISED,
            uri=destination_path,
            parents=None,
            children=None,
        )
        session.add(DataItem(**destination_values))
        session.add(migration)
        await session.flush()
        await session.refresh(migration)

        logger.info(
            "Queued migration %s from storage %s to %s using Rclone configurations %s and %s",
            migration.migration_id,
            source_storage_row.storage_id,
            destination_storage_row.storage_id,
            source_config_row.config_id,
            destination_config_row.config_id,
        )
        return {"uid": str(destination_uid), "migration_id": migration.migration_id}
