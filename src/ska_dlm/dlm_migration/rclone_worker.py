"""Worker that dispatches and tracks Rclone-backed data-item migrations."""

import asyncio
import logging
import os
import posixpath
import socket
import uuid
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import aliased, sessionmaker

from ska_dlm.common_types import ConfigType, ItemState
from ska_dlm.dlm_db import (
    DataItem,
    DataItemChildren,
    Migration,
    Storage,
    StorageConfig,
    get_async_database_url,
)
from ska_dlm.dlm_outbox.outbox import add_outbox_event

from ..embedded_rclone import Rclone, RcloneException, rclone_config_for_process
from .dlm_migration_requests import _migration_to_dict

logger = logging.getLogger(__name__)
_BATCH_SIZE = 50


class RcloneRPCClient(Protocol):
    """The embedded Rclone RPC surface used by the migration worker."""

    def rpc(self, method: str, **parameters: Any) -> dict[str, Any]:
        """Invoke an Rclone remote-control method."""
        ...


def _migration_database_url() -> str:
    """Return the database URL configured for the Rclone worker."""
    return get_async_database_url("DLM_RCLONE_WORKER_DATABASE_URL")


def _destination_uri(source_uri: str, source_root_uri: str, destination_root_uri: str) -> str:
    """Map a source tree URI to the corresponding destination URI."""
    relative_uri = posixpath.relpath(
        posixpath.normpath(source_uri),
        posixpath.normpath(source_root_uri),
    )
    if relative_uri == ".." or relative_uri.startswith(f"..{posixpath.sep}"):
        raise ValueError(
            f"Data item URI {source_uri!r} is outside source root {source_root_uri!r}"
        )
    if relative_uri == ".":
        return posixpath.normpath(destination_root_uri)
    return posixpath.normpath(posixpath.join(destination_root_uri, relative_uri))


def _rclone_backend(config: dict) -> str:
    """Build the Rclone backend path stored in a storage configuration."""
    name = config.get("name")
    if not name:
        raise ValueError("Rclone storage configuration has no backend name")
    return f"{name}:{config.get('root_path', '/')}"


def _storage_remote_path(root_directory: str, remote_path: str) -> str:
    """Resolve a storage-relative path beneath its configured root directory."""
    return posixpath.normpath(posixpath.join(root_directory or "/", remote_path.lstrip("/")))


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _copy_request(
    src_fs: str,
    src_remote: str,
    src_root_dir: str,
    dst_fs: str,
    dst_remote: str,
    dest_root_dir: str,
    item_type: str,
) -> tuple[str, dict]:
    """Build the Rclone RPC request for a file or container."""
    dest_abs_path = _storage_remote_path(dest_root_dir, dst_remote)
    if item_type == "container":
        return "sync/copy", {
            "srcFs": f"{src_fs}{src_root_dir}/{src_remote}",
            "dstFs": f"{dst_fs}{dest_abs_path}",
            "no-check-dest": True,
            "s3-no-check-bucket": True,
        }
    return "operations/copyfile", {
        "srcFs": f"{src_fs}{src_root_dir}",
        "srcRemote": src_remote,
        "dstFs": dst_fs,
        "dstRemote": dest_abs_path,
        "s3-no-check-bucket": True,
    }


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _execute_rclone_copy(
    rclone: RcloneRPCClient,
    source_config: dict,
    destination_config: dict,
    src_fs: str,
    src_remote: str,
    src_root_dir: str,
    dst_fs: str,
    dst_remote: str,
    dest_root_dir: str,
    item_type: str,
    execution_id: str,
) -> tuple[int, str]:
    """Create the required remotes and submit one asynchronous Rclone copy."""
    rclone.rpc("config/create", **rclone_config_for_process(source_config))
    rclone.rpc("config/create", **rclone_config_for_process(destination_config))
    method, parameters = _copy_request(
        src_fs,
        src_remote,
        src_root_dir,
        dst_fs,
        dst_remote,
        dest_root_dir,
        item_type,
    )
    parameters["_group"] = execution_id
    parameters["_async"] = True
    command = f"{method} {parameters}"
    response = rclone.rpc(method, **parameters)
    job_id = response.get("jobid")
    if not isinstance(job_id, int) or isinstance(job_id, bool):
        raise ValueError(f"Rclone {method} did not return a valid job ID")
    return job_id, command


def _poll_rclone_job(
    rclone: RcloneRPCClient, job_id: int, execution_id: str
) -> tuple[dict, dict | None]:
    """Read an asynchronous Rclone job's status and grouped transfer statistics."""
    status = rclone.rpc("job/status", jobid=job_id)
    if not isinstance(status.get("finished"), bool):
        raise ValueError(f"Rclone job {job_id} returned an invalid status")
    if not status["finished"]:
        return status, None
    if not isinstance(status.get("success"), bool):
        raise ValueError(f"Rclone job {job_id} returned an invalid completion status")
    try:
        stats = rclone.rpc("core/stats", group=execution_id)
    except RcloneException:
        logger.exception("Unable to retrieve Rclone statistics for job %s", job_id)
        stats = None
    return status, stats


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _item_copy_values(
    source_item: DataItem,
    destination_uid: uuid.UUID,
    destination_storage_id: uuid.UUID,
    destination_phase,
    destination_uri: str,
    uid_mapping: dict[uuid.UUID, uuid.UUID],
) -> dict:
    """Prepare a destination data-item row from its source row."""
    values = {
        attribute.key: getattr(source_item, attribute.key)
        for attribute in DataItem.__mapper__.column_attrs
        if attribute.key not in {"UID", "UID_creation", "UID_deletion"}
    }
    values["UID"] = destination_uid
    values["UID_deletion"] = None
    values["storage_id"] = destination_storage_id
    values["UID_phase"] = destination_phase
    values["item_state"] = ItemState.READY
    values["uri"] = destination_uri
    for relation in ("parents", "children"):
        related_uid = values.get(relation)
        if related_uid is not None:
            values[relation] = uid_mapping.get(related_uid)
    return values


async def _load_source_tree(
    session: AsyncSession, root_uid: uuid.UUID
) -> tuple[dict[uuid.UUID, DataItem], list[tuple[uuid.UUID, uuid.UUID]]]:
    """Load all data items and parent-child edges reachable from a root item."""
    items = {root_uid: await session.scalar(select(DataItem).where(DataItem.UID == root_uid))}
    if items[root_uid] is None:
        return {}, []

    edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
    frontier = [root_uid]
    while frontier:
        result = await session.execute(
            select(
                DataItemChildren.parent_data_item_uid,
                DataItemChildren.data_item_uid,
            )
            .where(DataItemChildren.parent_data_item_uid.in_(frontier))
            .with_for_update()
        )
        new_uids: set[uuid.UUID] = set()
        for parent_uid, child_uid in result:
            edges.add((parent_uid, child_uid))
            if child_uid not in items:
                new_uids.add(child_uid)
        legacy_children = await session.execute(
            select(DataItem.UID, DataItem.parents)
            .where(DataItem.parents.in_(frontier))
            .with_for_update()
        )
        for child_uid, parent_uid in legacy_children:
            edges.add((parent_uid, child_uid))
            if child_uid not in items:
                new_uids.add(child_uid)

        if not new_uids:
            break
        child_items = (
            await session.scalars(
                select(DataItem).where(DataItem.UID.in_(new_uids)).with_for_update()
            )
        ).all()
        items.update({item.UID: item for item in child_items})
        missing_uids = new_uids - items.keys()
        if missing_uids:
            raise ValueError(f"Data-item tree contains missing children: {missing_uids}")
        frontier = list(new_uids)

    return items, list(edges)


# pylint: disable=too-many-locals
async def _create_destination_tree(
    session: AsyncSession,
    migration: Migration,
    source_item: DataItem,
    destination_storage: Storage,
) -> None:
    """Create destination data-item rows and child edges in the active transaction."""
    source_items, edges = await _load_source_tree(session, source_item.UID)
    if not source_items:
        raise ValueError(f"Source data item {source_item.UID} no longer exists")

    destination_root_uid = migration.destination_uid or uuid.uuid4()
    migration.destination_uid = destination_root_uid
    uid_mapping = {
        source_uid: destination_root_uid if source_uid == source_item.UID else uuid.uuid4()
        for source_uid in source_items
    }
    existing_destination = await session.scalar(
        select(DataItem).where(DataItem.UID == destination_root_uid).with_for_update()
    )
    source_root_uri = source_item.uri or migration.destination_path or ""
    destination_root_uri = (
        migration.destination_path
        or (existing_destination.uri if existing_destination is not None else None)
        or source_root_uri
    )

    for source_uid, source_node in source_items.items():
        destination_uri = _destination_uri(
            source_node.uri or source_root_uri,
            source_root_uri,
            destination_root_uri,
        )
        copy_values = _item_copy_values(
            source_node,
            uid_mapping[source_uid],
            destination_storage.storage_id,
            destination_storage.storage_phase,
            destination_uri,
            uid_mapping,
        )
        if existing_destination is not None and source_uid == source_item.UID:
            for key, value in copy_values.items():
                if key != "UID":
                    setattr(existing_destination, key, value)
        else:
            session.add(DataItem(**copy_values))
    await session.flush()

    if edges:
        await session.execute(
            pg_insert(DataItemChildren)
            .values(
                [
                    {
                        "parent_data_item_uid": uid_mapping[parent_uid],
                        "data_item_uid": uid_mapping[child_uid],
                    }
                    for parent_uid, child_uid in edges
                ]
            )
            .on_conflict_do_nothing(constraint="uq_data_item_children_parent_child")
        )


async def _lock_source_item(session: AsyncSession, migration: Migration) -> DataItem | None:
    """Lock and load the source item without changing its state."""
    if migration.uid is None:
        return None
    source_item = await session.scalar(
        select(DataItem).where(DataItem.UID == migration.uid).with_for_update()
    )
    return source_item


async def _cleanup_partial_destination(
    session: AsyncSession, migration: Migration, rclone: Rclone
) -> None:
    """Best-effort removal of partial transfer data and any legacy destination rows."""
    destination_config = await session.scalar(
        select(StorageConfig)
        .where(
            StorageConfig.storage_id == migration.destination_storage_id,
            StorageConfig.config_type == ConfigType.RCLONE,
        )
        .order_by(StorageConfig.config_date)
        .limit(1)
    )
    destination_storage = await session.scalar(
        select(Storage).where(Storage.storage_id == migration.destination_storage_id)
    )
    if (
        destination_config is not None
        and destination_storage is not None
        and migration.destination_path
    ):
        try:
            config = destination_config.config
            fs = _rclone_backend(config)
            operation = "purge" if await _source_is_container(session, migration) else "deletefile"
            await asyncio.to_thread(
                rclone.rpc,
                "config/create",
                **rclone_config_for_process(config),
            )
            try:
                await asyncio.to_thread(
                    rclone.rpc,
                    f"operations/{operation}",
                    fs=fs,
                    remote=_storage_remote_path(
                        destination_storage.root_directory or "/",
                        migration.destination_path,
                    ),
                )
            except RcloneException:
                if operation != "purge":
                    raise
                await asyncio.to_thread(
                    rclone.rpc,
                    "operations/deletefile",
                    fs=fs,
                    remote=_storage_remote_path(
                        destination_storage.root_directory or "/",
                        migration.destination_path,
                    ),
                )
        except (OSError, RcloneException, TypeError, ValueError):
            logger.exception(
                "Failed to clean up partial Rclone destination for migration %s",
                migration.migration_id,
            )

    if migration.destination_uid is None:
        return
    destination_items, _ = await _load_source_tree(session, migration.destination_uid)
    destination_uids = list(destination_items)
    if destination_uids:
        await session.execute(
            delete(DataItemChildren).where(
                or_(
                    DataItemChildren.parent_data_item_uid.in_(destination_uids),
                    DataItemChildren.data_item_uid.in_(destination_uids),
                )
            )
        )
        await session.execute(delete(DataItem).where(DataItem.UID.in_(destination_uids)))


async def _source_is_container(session: AsyncSession, migration: Migration) -> bool:
    """Return whether the source item is a container."""
    for item_uid in (migration.uid, migration.destination_uid):
        if item_uid is not None:
            item = await session.scalar(select(DataItem).where(DataItem.UID == item_uid))
            if item is not None:
                return item.item_type == "container"
    return False


async def _finish_migration(
    session: AsyncSession,
    migration: Migration,
    rclone: Rclone,
    status_json: dict,
    stats_json: dict | None,
    *,
    success: bool,
) -> None:
    """Persist terminal job status and its transactional data-item changes."""
    migration.job_status = status_json
    migration.job_stats = stats_json
    migration.complete = True
    migration.completion_date = datetime.now()
    source_item = await _lock_source_item(session, migration)
    if success and source_item is None:
        status_json = dict(status_json)
        status_json["success"] = False
        status_json["error"] = "Source data item no longer exists"
        migration.job_status = status_json
        success = False
    if success and source_item is not None:
        destination_storage = await session.scalar(
            select(Storage).where(Storage.storage_id == migration.destination_storage_id)
        )
        if destination_storage is None:
            raise ValueError(
                f"Destination storage {migration.destination_storage_id} no longer exists"
            )
        await _create_destination_tree(session, migration, source_item, destination_storage)
    else:
        await _cleanup_partial_destination(session, migration, rclone)
    await add_outbox_event(
        session=session,
        event_type="dlm.migration.update",
        payload=_migration_to_dict(migration),
    )


async def _migration_ids(session_factory, worker_id: str) -> list[int]:
    """Find queued migrations and active jobs owned by this worker."""
    async with session_factory() as session:
        result = await session.scalars(
            select(Migration.migration_id)
            .where(Migration.complete.is_(False))
            .where(
                or_(
                    and_(
                        Migration.job_id.is_(None),
                        Migration.execution_id.is_(None),
                    ),
                    and_(
                        Migration.job_id.is_not(None),
                        Migration.host_id == worker_id,
                    ),
                )
            )
            .order_by(Migration.date)
            .limit(_BATCH_SIZE)
        )
        return list(result.all())


async def _recover_owned_migrations(session_factory, rclone: Rclone, worker_id: str) -> int:
    """Clean up and requeue this worker's migrations after an Rclone restart."""
    async with session_factory() as session:
        async with session.begin():
            migrations = (
                await session.scalars(
                    select(Migration)
                    .where(
                        Migration.complete.is_(False),
                        Migration.host_id == worker_id,
                    )
                    .order_by(Migration.date)
                    .with_for_update()
                )
            ).all()
            for migration in migrations:
                await _cleanup_partial_destination(session, migration, rclone)
                migration.job_id = None
                migration.execution_id = None
                migration.host_id = None
                migration.command = None
                migration.job_status = None
                migration.job_stats = None
            return len(migrations)


# pylint: disable=too-many-locals
async def _dispatch_migration(
    session_factory,
    migration_id: int,
    rclone: Rclone,
    worker_id: str,
) -> bool:
    """Submit queued migrations and poll Rclone jobs owned by this worker."""
    async with session_factory() as session:
        async with session.begin():
            migration = await session.scalar(
                select(Migration)
                .where(
                    Migration.migration_id == migration_id,
                    Migration.complete.is_(False),
                    or_(
                        and_(
                            Migration.job_id.is_(None),
                            Migration.execution_id.is_(None),
                        ),
                        and_(
                            Migration.job_id.is_not(None),
                            Migration.host_id == worker_id,
                        ),
                    ),
                )
                .with_for_update(skip_locked=True)
            )
            if migration is None:
                return False

            if migration.job_id is not None:
                if migration.execution_id is None:
                    await _finish_migration(
                        session,
                        migration,
                        rclone,
                        {
                            "finished": True,
                            "success": False,
                            "error": "Rclone job has no execution ID",
                        },
                        None,
                        success=False,
                    )
                    return True
                try:
                    status_json, stats_json = await asyncio.to_thread(
                        _poll_rclone_job,
                        rclone,
                        migration.job_id,
                        str(migration.execution_id),
                    )
                except (
                    RcloneException,
                    OSError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as exc:
                    logger.exception(
                        "Failed to poll Rclone job %s for migration %s",
                        migration.job_id,
                        migration_id,
                    )
                    status_json = dict(exc.output) if isinstance(exc, RcloneException) else {}
                    status_json.update(finished=True, success=False, error=str(exc))
                    await _finish_migration(
                        session,
                        migration,
                        rclone,
                        status_json,
                        None,
                        success=False,
                    )
                    return True

                migration.job_status = status_json
                migration.job_stats = stats_json
                if not status_json["finished"]:
                    return True
                await _finish_migration(
                    session,
                    migration,
                    rclone,
                    status_json,
                    stats_json,
                    success=status_json.get("success") is True,
                )
                return True

            source_item = None
            if migration.uid is not None:
                source_item = await session.scalar(
                    select(DataItem).where(DataItem.UID == migration.uid).with_for_update()
                )
            if source_item is None:
                await _finish_migration(
                    session,
                    migration,
                    rclone,
                    {"finished": True, "success": False, "error": "Source data item not found"},
                    None,
                    success=False,
                )
                return True

            source_storage = aliased(Storage)
            destination_storage = aliased(Storage)
            source_config = aliased(StorageConfig)
            destination_config = aliased(StorageConfig)
            config_rows = (
                await session.execute(
                    select(
                        source_storage,
                        source_config,
                        destination_storage,
                        destination_config,
                    )
                    .join(
                        source_config,
                        source_config.storage_id == source_storage.storage_id,
                    )
                    .join(
                        destination_storage,
                        destination_storage.storage_id == migration.destination_storage_id,
                    )
                    .join(
                        destination_config,
                        destination_config.storage_id == destination_storage.storage_id,
                    )
                    .where(source_storage.storage_id == migration.source_storage_id)
                    .where(source_config.config_type == ConfigType.RCLONE)
                    .where(destination_config.config_type == ConfigType.RCLONE)
                    .order_by(source_config.config_date, destination_config.config_date)
                    .limit(1)
                )
            ).first()
            if config_rows is None:
                await _finish_migration(
                    session,
                    migration,
                    rclone,
                    {
                        "finished": True,
                        "success": False,
                        "error": "Storage Rclone configuration not found",
                    },
                    None,
                    success=False,
                )
                return True

            (
                source_storage_row,
                source_config_row,
                destination_storage_row,
                destination_config_row,
            ) = config_rows
            source_config_data = source_config_row.config
            destination_config_data = destination_config_row.config
            execution_id = uuid.uuid4()
            migration.execution_id = execution_id
            migration.host_id = worker_id

            try:
                job_id, command = await asyncio.to_thread(
                    _execute_rclone_copy,
                    rclone,
                    source_config_data,
                    destination_config_data,
                    _rclone_backend(source_config_data),
                    source_item.uri or "",
                    source_storage_row.root_directory or "/",
                    _rclone_backend(destination_config_data),
                    migration.destination_path or source_item.uri or "",
                    destination_storage_row.root_directory or "/",
                    source_item.item_type,
                    str(execution_id),
                )
                migration.job_id = job_id
                migration.command = command
                migration.job_status = {"finished": False}
            except (
                RcloneException,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                logger.exception("Failed to submit migration %s to Rclone", migration_id)
                status_json = dict(exc.output) if isinstance(exc, RcloneException) else {}
                status_json.update(finished=True, success=False, error=str(exc))
                await _finish_migration(
                    session,
                    migration,
                    rclone,
                    status_json,
                    None,
                    success=False,
                )
            return True


async def _run_worker_iteration(session_factory, rclone: Rclone, worker_id: str) -> bool:
    """Submit queued migrations and poll their active Rclone jobs."""
    did_work = False
    for migration_id in await _migration_ids(session_factory, worker_id):
        did_work = (
            await _dispatch_migration(session_factory, migration_id, rclone, worker_id) or did_work
        )
    return did_work


async def run_worker() -> None:
    """Run the Rclone migration worker until shutdown."""
    poll_interval = int(
        os.getenv(
            "DLM_RCLONE_WORKER_POLL_INTERVAL",
            "10",
        )
    )
    worker_id = os.getenv("DLM_RCLONE_WORKER_ID", socket.gethostname())
    rclone = Rclone()
    engine = create_async_engine(
        _migration_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    session_factory = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        future=True,
    )
    logger.info("Starting Rclone migration worker %s", worker_id)
    recovery_complete = False
    try:
        while True:
            try:
                if not recovery_complete:
                    recovered_count = await _recover_owned_migrations(
                        session_factory, rclone, worker_id
                    )
                    logger.info(
                        "Recovered %s unfinished migrations owned by worker %s",
                        recovered_count,
                        worker_id,
                    )
                    recovery_complete = True
                await _run_worker_iteration(session_factory, rclone, worker_id)
            except (
                SQLAlchemyError,
                OSError,
                RcloneException,
                KeyError,
                TypeError,
                ValueError,
                RuntimeError,
            ):
                logger.exception("Unexpected migration worker failure")
            await asyncio.sleep(poll_interval)
    finally:
        await engine.dispose()
        rclone.close()


def main() -> None:
    """Run the Rclone migration worker entry point."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
