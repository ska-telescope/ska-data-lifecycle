"""Worker that dispatches and tracks Rclone-backed data-item migrations."""

# pylint: disable=too-many-lines

import asyncio
import hashlib
import json
import logging
import os
import posixpath
import socket
import uuid
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import and_, or_, select
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
_S3_RETRY_CONFIG_KEY = "leave_parts_on_error"


class RcloneRPCClient(Protocol):  # pylint: disable=too-few-public-methods
    """The embedded Rclone RPC surface used by the migration worker."""

    def rpc(self, method: str, **parameters: Any) -> dict[str, Any]:
        """Invoke an Rclone remote-control method."""
        ...  # pylint: disable=unnecessary-ellipsis


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


def _migration_stage_path(destination_path: str, destination_uid: uuid.UUID) -> str:
    """Return a stable, migration-owned sibling path for retries."""
    return f"{destination_path.rstrip('/')}.dlm-staging-{destination_uid.hex}"


def _s3_retry_enabled(config: dict) -> bool:
    """Return whether an S3 backend explicitly opted into automatic retries."""
    parameters = config.get("parameters")
    return (
        config.get("type") == "s3"
        and isinstance(parameters, dict)
        and parameters.get(_S3_RETRY_CONFIG_KEY) is True
    )


def _content_fingerprint(rclone: RcloneRPCClient, fs_path: str, *, is_container: bool) -> str:
    """Hash every file's bytes and relative path without trusting backend hashes."""
    result = rclone.rpc(
        "operations/hashsum",
        fs=fs_path,
        hashType="SHA-256",
        # Download bytes to avoid trusting backend-provided checksums or metadata.
        download=True,
    )
    hashes = result.get("hashsum")
    if not isinstance(hashes, list) or not all(isinstance(item, str) for item in hashes):
        raise ValueError(f"Rclone could not verify content at {fs_path}")
    normalized = []
    for item in hashes:
        digest, separator, path = item.partition("  ")
        if not separator or not digest:
            raise ValueError(f"Rclone returned an invalid content hash for {fs_path}")
        # Container paths distinguish files; a standalone file's remote name is immaterial.
        normalized.append((path if is_container else "", digest))
    # Sort before hashing so Rclone's result order does not affect the snapshot.
    payload = json.dumps(sorted(normalized), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def _verify_and_publish(
    rclone: RcloneRPCClient,
    source_config: dict,
    destination_config: dict,
    source_storage_root: str,
    source_uri: str,
    destination_storage_root: str,
    destination_uri: str,
    staging_uri: str,
    item_type: str,
    source_fingerprint: str,
) -> None:
    """Verify source and staged bytes, then publish only to an absent destination."""
    source_fs = _rclone_backend(source_config)
    destination_fs = _rclone_backend(destination_config)
    source_path = _storage_remote_path(source_storage_root, source_uri)
    destination_path = _storage_remote_path(destination_storage_root, destination_uri)
    staging_path = _storage_remote_path(destination_storage_root, staging_uri)
    is_container = item_type == "container"

    rclone.rpc("config/create", **rclone_config_for_process(source_config))
    rclone.rpc("config/create", **rclone_config_for_process(destination_config))
    current_source_fingerprint = _content_fingerprint(
        rclone, f"{source_fs}{source_path}", is_container=is_container
    )
    if current_source_fingerprint != source_fingerprint:
        raise ValueError("Source content changed during migration; refusing to publish")

    destination_info = rclone.rpc("operations/stat", fs=destination_fs, remote=destination_path)
    stage_info = rclone.rpc("operations/stat", fs=destination_fs, remote=staging_path)
    if stage_info.get("item") is None:
        if destination_info.get("item") is not None:
            # A previous attempt may have moved the stage before crashing; accept only
            # the exact snapshot, never an unrelated object at the final path.
            published_fingerprint = _content_fingerprint(
                rclone, f"{destination_fs}{destination_path}", is_container=is_container
            )
            if published_fingerprint == source_fingerprint:
                return
            raise ValueError("Destination exists but does not match the migration snapshot")
        raise ValueError("Verified migration staging data is missing")
    staged_fingerprint = _content_fingerprint(
        rclone, f"{destination_fs}{staging_path}", is_container=is_container
    )
    if staged_fingerprint != source_fingerprint:
        raise ValueError("Staged content does not match the source snapshot")
    if destination_info.get("item") is not None:
        # Rclone cannot provide a portable atomic no-clobber move across backends.
        raise ValueError(
            "Destination already exists; overwrite is not supported because replacement "
            "cannot be guaranteed crash-safe"
        )

    if is_container:
        rclone.rpc(
            "sync/move",
            srcFs=f"{destination_fs}{staging_path}",
            dstFs=f"{destination_fs}{destination_path}",
        )
    else:
        rclone.rpc(
            "operations/movefile",
            srcFs=destination_fs,
            srcRemote=staging_path,
            dstFs=destination_fs,
            dstRemote=destination_path,
        )


# pylint: disable=too-many-locals
async def _submit_s3_retry(
    session: AsyncSession,
    migration: Migration,
    rclone: Rclone,
    worker_id: str,
    worker_state: dict,
) -> bool:
    """Retry an opted-in S3 transfer against the same staging object."""
    source_item = await _lock_source_item(session, migration)
    if source_item is None:
        return False
    try:
        (
            source_storage,
            source_config,
            destination_storage,
            destination_config,
        ) = await _load_copy_context(session, migration)
        source_config_data = source_config.config
        destination_config_data = destination_config.config
        if not _s3_retry_enabled(destination_config_data):
            return False

        source_fingerprint = worker_state.get("source_fingerprint")
        staging_path = worker_state.get("staging_path")
        if not isinstance(source_fingerprint, str) or not isinstance(staging_path, str):
            raise ValueError("S3 retry is missing its source snapshot or staging path")
        source_path = (
            f"{_rclone_backend(source_config_data)}"
            f"{_storage_remote_path(source_storage.root_directory or '/', source_item.uri or '')}"
        )
        current_fingerprint = await asyncio.to_thread(
            _content_fingerprint,
            rclone,
            source_path,
            is_container=source_item.item_type == "container",
        )
        if current_fingerprint != source_fingerprint:
            raise ValueError("Source content changed between retries; refusing to continue")

        # This resubmits a full copy to the stable staging key; Rclone does not resume
        # the previous multipart upload.
        execution_id = uuid.uuid4()
        job_id, command = await asyncio.to_thread(
            _execute_rclone_copy,
            rclone,
            source_config_data,
            destination_config_data,
            _rclone_backend(source_config_data),
            source_item.uri or "",
            source_storage.root_directory or "/",
            _rclone_backend(destination_config_data),
            staging_path,
            destination_storage.root_directory or "/",
            source_item.item_type,
            str(execution_id),
        )
        worker_state = {**worker_state, "retry_count": worker_state.get("retry_count", 0) + 1}
        migration.job_id = job_id
        migration.execution_id = execution_id
        migration.host_id = worker_id
        migration.command = command
        migration.job_status = {"finished": False, "_dlm_worker": worker_state}
        migration.job_stats = None
        logger.warning(
            "Retrying failed S3 migration %s against its existing staging key (attempt %s)",
            migration.migration_id,
            worker_state["retry_count"] + 1,
        )
        return True
    except (OSError, RcloneException, RuntimeError, TypeError, ValueError) as exc:
        logger.exception("Unable to safely retry S3 migration %s", migration.migration_id)
        migration.job_id = None
        migration.job_status = {
            "finished": False,
            "reconciliation_required": True,
            "error": f"S3 retry stopped: {exc}",
            "_dlm_worker": worker_state,
        }
        return False


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


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
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
        # Read the legacy parents column as well while older rows may still use it.
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
    # Keep the UID reserved when the migration was requested; derive child UIDs separately.
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


async def _load_copy_context(session: AsyncSession, migration: Migration):
    """Load source and destination storage configurations for one migration."""
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
            .join(source_config, source_config.storage_id == source_storage.storage_id)
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
        raise ValueError("Storage Rclone configuration not found")
    return config_rows


async def _cleanup_partial_destination(
    session: AsyncSession, migration: Migration, rclone: Rclone
) -> None:
    """Preserve destinations whose ownership cannot be established."""
    del session, rclone
    logger.warning(
        "Migration %s may have left partial data at %s; manual inspection is required",
        migration.migration_id,
        migration.destination_path,
    )


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
        worker_state = status_json.get("_dlm_worker", {})
        try:
            if not isinstance(worker_state, dict):
                raise ValueError("Migration worker state is invalid")
            (
                source_storage_row,
                source_config_row,
                _,
                destination_config_row,
            ) = await _load_copy_context(session, migration)
            staging_path = worker_state.get("staging_path")
            source_fingerprint = worker_state.get("source_fingerprint")
            if not isinstance(staging_path, str) or not isinstance(source_fingerprint, str):
                raise ValueError("Migration staging or source snapshot is missing")
            # Publication may be replayed after a crash; _verify_and_publish recognizes
            # an already-moved destination only when its bytes match this snapshot.
            await asyncio.to_thread(
                _verify_and_publish,
                rclone,
                source_config_row.config,
                destination_config_row.config,
                source_storage_row.root_directory or "/",
                source_item.uri or "",
                destination_storage.root_directory or "/",
                migration.destination_path or source_item.uri or "",
                staging_path,
                source_item.item_type,
                source_fingerprint,
            )
        except (OSError, RcloneException, TypeError, ValueError) as exc:
            status_json = dict(status_json)
            status_json.update(success=False, error=str(exc))
            migration.job_status = status_json
            success = False
        if success:
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
                        Migration.job_status["reconciliation_required"].as_boolean().is_not(True),
                    ),
                    and_(
                        Migration.job_id.is_not(None),
                        Migration.host_id.is_(None),
                        Migration.execution_id.is_(None),
                    ),
                )
            )
            .order_by(Migration.date)
            .limit(_BATCH_SIZE)
        )
        return list(result.all())


async def _recover_owned_migrations(session_factory, rclone: Rclone, worker_id: str) -> int:
    """Requeue resumable S3 stages and quarantine other uncertain jobs."""
    del rclone
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
                status = dict(migration.job_status or {})
                worker_state = status.get("_dlm_worker", {})
                # Resume only copies with an owned stage or a durable publish intent.
                # Other in-flight jobs have an ambiguous external outcome.
                if _can_resume_worker_state(status, worker_state):
                    migration.job_id = None
                    migration.execution_id = None
                    migration.host_id = None
                    migration.command = None
                    migration.job_stats = None
                    migration.job_status = {
                        "finished": False,
                        "_dlm_worker": worker_state,
                    }
                    continue
                status["reconciliation_required"] = True
                status["error"] = (
                    "Worker restarted with an unfinished job; stop any old worker and "
                    "inspect its destination before manually reconciling this migration"
                )
                migration.job_status = status
            return len(migrations)


def _can_resume_worker_state(status: dict, worker_state: Any) -> bool:
    """Return whether persisted staging metadata makes a migration resumable."""
    return (
        status.get("reconciliation_required") is not True
        and isinstance(worker_state, dict)
        and isinstance(worker_state.get("staging_path"), str)
        and isinstance(worker_state.get("source_fingerprint"), str)
        and (
            worker_state.get("s3_retry_enabled") is True
            or worker_state.get("publication_pending") is True
        )
    )


# pylint: disable=too-many-return-statements
async def _dispatch_active_job(
    session: AsyncSession,
    migration: Migration,
    rclone: Rclone,
    worker_id: str,
    migration_id: int,
) -> bool:
    """Poll a claimed job, retry it when allowed, or persist its terminal state."""
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

    worker_state = (migration.job_status or {}).get("_dlm_worker", {})
    stored_status = migration.job_status or {}
    if stored_status.get("finished") is True:
        status_json, stats_json = stored_status, migration.job_stats
    else:
        try:
            status_json, stats_json = await asyncio.to_thread(
                _poll_rclone_job,
                rclone,
                migration.job_id,
                str(migration.execution_id),
            )
        except (RcloneException, OSError, RuntimeError, TypeError, ValueError):
            logger.exception(
                "Failed to poll Rclone job %s for migration %s",
                migration.job_id,
                migration_id,
            )
            return False

    migration.job_status = status_json
    migration.job_stats = stats_json
    if not status_json["finished"]:
        status_json["_dlm_worker"] = worker_state
        migration.job_status = status_json
        return True
    if (
        status_json.get("success") is True
        and isinstance(worker_state, dict)
        and worker_state.get("publication_pending") is not True
    ):
        # Commit intent in this iteration before the next one touches destination data.
        worker_state = {**worker_state, "publication_pending": True}
        status_json["_dlm_worker"] = worker_state
        migration.job_status = status_json
        return True
    if (
        status_json.get("success") is not True
        and isinstance(worker_state, dict)
        and worker_state.get("s3_retry_enabled") is True
    ):
        if await _submit_s3_retry(session, migration, rclone, worker_id, worker_state):
            return True
        if migration.job_status.get("reconciliation_required"):
            return True

    status_json["_dlm_worker"] = worker_state
    await _finish_migration(
        session,
        migration,
        rclone,
        status_json,
        stats_json,
        success=status_json.get("success") is True,
    )
    return True


async def _dispatch_migration(
    session_factory,
    migration_id: int,
    rclone: Rclone,
    worker_id: str,
) -> bool:
    """Submit queued migrations and poll Rclone jobs owned by this worker."""
    async with session_factory() as session:
        async with session.begin():
            # Locking with skip_locked lets another worker claim a different migration
            # instead of blocking behind this one.
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
                        and_(
                            Migration.job_id.is_not(None),
                            Migration.host_id.is_(None),
                            Migration.execution_id.is_(None),
                        ),
                    ),
                )
                .with_for_update(skip_locked=True)
            )
            if migration is None:
                return False

            if migration.job_id is not None and migration.host_id is None:
                await _finish_migration(
                    session,
                    migration,
                    rclone,
                    {
                        "finished": True,
                        "success": False,
                        "error": (
                            "Legacy Rclone daemon job has no worker owner. Stop the old daemon, "
                            "inspect its payload, and manually retry the migration."
                        ),
                    },
                    None,
                    success=False,
                )
                return True

            if (migration.job_status or {}).get("reconciliation_required"):
                return False

            if migration.job_id is not None:
                return await _dispatch_active_job(
                    session, migration, rclone, worker_id, migration_id
                )

            return await _dispatch_queued_migration(
                session, migration, rclone, worker_id, migration_id
            )


async def _dispatch_queued_migration(
    session: AsyncSession,
    migration: Migration,
    rclone: Rclone,
    worker_id: str,
    migration_id: int,
) -> bool:
    """Prepare a staged copy and submit it to Rclone."""
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

    worker_state = dict((migration.job_status or {}).get("_dlm_worker", {}))
    if worker_state.get("publication_pending") is True:
        await _finish_migration(
            session,
            migration,
            rclone,
            {"finished": True, "success": True, "_dlm_worker": worker_state},
            migration.job_stats,
            success=True,
        )
        return True

    try:
        config_rows = await _load_copy_context(session, migration)
    except ValueError:
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
    destination_path = migration.destination_path or source_item.uri or ""
    if not destination_path or migration.destination_uid is None:
        await _finish_migration(
            session,
            migration,
            rclone,
            {
                "finished": True,
                "success": False,
                "error": "Destination path or UID missing",
            },
            None,
            success=False,
        )
        return True

    stage_path = worker_state.get("staging_path") or _migration_stage_path(
        destination_path, migration.destination_uid
    )
    try:
        await asyncio.to_thread(
            rclone.rpc,
            "config/create",
            **rclone_config_for_process(source_config_data),
        )
        await asyncio.to_thread(
            rclone.rpc,
            "config/create",
            **rclone_config_for_process(destination_config_data),
        )
        source_fingerprint = worker_state.get("source_fingerprint")
        if source_fingerprint is None:
            # Never adopt a leftover stage unless its ownership and source snapshot
            # were persisted by this migration.
            stage_info = await asyncio.to_thread(
                rclone.rpc,
                "operations/stat",
                fs=_rclone_backend(destination_config_data),
                remote=_storage_remote_path(
                    destination_storage_row.root_directory or "/", stage_path
                ),
            )
            if stage_info.get("item") is not None:
                raise ValueError(
                    "Migration staging path already exists without a saved owner record"
                )
            source_remote_path = _storage_remote_path(
                source_storage_row.root_directory or "/", source_item.uri or ""
            )
            source_fs_path = f"{_rclone_backend(source_config_data)}{source_remote_path}"
            source_fingerprint = await asyncio.to_thread(
                _content_fingerprint,
                rclone,
                source_fs_path,
                is_container=source_item.item_type == "container",
            )
        worker_state.update(
            staging_path=stage_path,
            source_fingerprint=source_fingerprint,
            s3_retry_enabled=_s3_retry_enabled(destination_config_data),
            retry_count=worker_state.get("retry_count", 0),
        )
        migration.job_status = {"_dlm_worker": worker_state}
    except (OSError, RcloneException, RuntimeError, TypeError, ValueError) as exc:
        await _finish_migration(
            session,
            migration,
            rclone,
            {
                "finished": True,
                "success": False,
                "error": f"Unable to prepare migration staging: {exc}",
            },
            None,
            success=False,
        )
        return True

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
            stage_path,
            destination_storage_row.root_directory or "/",
            source_item.item_type,
            str(execution_id),
        )
        migration.job_id = job_id
        migration.command = command
        migration.job_status = {"finished": False, "_dlm_worker": worker_state}
    except (RcloneException, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.exception("Failed to submit migration %s to Rclone", migration_id)
        # A lost RPC response may hide a successful submission, so quarantine instead
        # of launching a duplicate copy.
        status_json = dict(exc.output) if isinstance(exc, RcloneException) else {}
        status_json.update(
            finished=False,
            reconciliation_required=True,
            error=(
                f"Rclone submission outcome is uncertain: {exc}. "
                "Stop the worker and inspect the destination before manual reconciliation."
            ),
            _dlm_worker=worker_state,
        )
        migration.job_status = status_json
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
