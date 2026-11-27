"""Tests for Rclone migration-worker helpers."""

# pylint: disable=too-many-lines

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ska_dlm import embedded_rclone
from ska_dlm.common_types import ItemState, PhaseType
from ska_dlm.dlm_db import DataItem
from ska_dlm.dlm_migration import dlm_migration_requests, rclone_worker
from ska_dlm.dlm_migration.rclone_worker import (
    _copy_request,
    _destination_uri,
    _dispatch_migration,
    _execute_rclone_copy,
    _item_copy_values,
    _migration_stage_path,
    _poll_rclone_job,
    _recover_owned_migrations,
    _remote_retry_enabled,
    _storage_remote_path,
    _verify_and_publish,
)
from ska_dlm.exceptions import UnmetPreconditionForOperation


class _Transaction:
    """Minimal async transaction context manager."""

    async def __aenter__(self):
        """Enter the fake transaction."""
        return self

    async def __aexit__(self, *_exc_info):
        """Leave the fake transaction."""
        return False


class _MigrationSession:
    """Capture the source query and return a configured source item."""

    def __init__(self, source_item, active_migration_id=None, storage_rows=None):
        self.source_item = source_item
        self.statement = None
        self.statements = []
        self.active_migration_id = active_migration_id
        self.scalar_calls = 0
        self.storage_rows = storage_rows
        self.added = []

    async def scalars(self, _statement):
        """Return no conflicting destination reservations."""
        return SimpleNamespace(all=lambda: [])

    def in_transaction(self):
        """Report that the session has not started a transaction."""
        return False

    def begin(self):
        """Start a fake transaction."""
        return _Transaction()

    async def scalar(self, statement):
        """Return the configured source or active-migration row."""
        self.statement = statement
        self.statements.append(statement)
        self.scalar_calls += 1
        return self.source_item if self.scalar_calls == 1 else self.active_migration_id

    async def execute(self, _statement):
        """Return configured storage and Rclone configuration rows."""
        return SimpleNamespace(first=lambda: self.storage_rows)

    def add(self, value):
        """Capture a pending ORM row."""
        self.added.append(value)

    async def flush(self):
        """Accept pending ORM rows."""

    async def refresh(self, migration):
        """Populate the generated migration ID."""
        migration.migration_id = 1


def test_destination_uri_maps_relative_tree_paths():
    """Child URIs retain their path relative to the copied container root."""
    assert (
        _destination_uri(
            "/source/container/dir/file",
            "/source/container/",
            "/destination/container",
        )
        == "/destination/container/dir/file"
    )


def test_destination_uri_rejects_paths_outside_the_root():
    """The worker must not map an unrelated source path into the destination tree."""
    with pytest.raises(ValueError, match="outside source root"):
        _destination_uri("/source/other/file", "/source/container", "/destination/container")


def test_storage_remote_path_includes_storage_root():
    """Copies and failure cleanup address paths beneath the storage root."""
    assert _storage_remote_path("/archive/root", "/destination/file") == (
        "/archive/root/destination/file"
    )


def test_stage_path_is_stable_and_separate_from_destination():
    """Retries use the same path without targeting the final destination."""
    destination_uid = uuid.uuid4()

    first = _migration_stage_path("/destination/file", destination_uid)
    second = _migration_stage_path("/destination/file", destination_uid)

    assert first == second
    assert first != "/destination/file"
    assert first.endswith(destination_uid.hex)


@pytest.mark.parametrize(
    ("source", "destination", "expected"),
    [
        ({"type": "alias"}, {"type": "s3"}, True),
        ({"type": "sftp"}, {"type": "alias"}, True),
        ({"type": "s3"}, {"type": "sftp"}, True),
        ({"type": "alias"}, {"type": "alias"}, False),
    ],
)
def test_remote_retry_supports_s3_and_sftp(source, destination, expected):
    """Retry eligibility includes S3 or SFTP on either side of the transfer."""
    assert _remote_retry_enabled(source, destination) is expected


@pytest.mark.parametrize("backend", ["s3", "sftp", "alias"])
@pytest.mark.parametrize("item_type", ["file", "container"])
def test_publication_moves_verified_data_when_destination_absent(monkeypatch, backend, item_type):
    """Best-effort publication uses the appropriate move for files and containers."""
    source_config = {"name": "source", "type": "alias", "parameters": {}}
    destination_config = {"name": "destination", "type": backend, "parameters": {}}
    rclone = mock.Mock()
    rclone.rpc.side_effect = lambda method, **kwargs: (
        {"item": {"Name": "stage"} if kwargs["remote"].endswith("staging") else None}
        if method == "operations/stat"
        else {}
    )
    fingerprint = mock.Mock(return_value="snapshot")
    monkeypatch.setattr(rclone_worker, "_content_fingerprint", fingerprint)
    _verify_and_publish(
        rclone,
        source_config,
        destination_config,
        "/",
        "/source/file",
        "/",
        "/destination/file",
        "/destination/file.staging",
        item_type,
        "snapshot",
    )
    methods = [call.args[0] for call in rclone.rpc.call_args_list]
    assert methods.count("sync/move" if item_type == "container" else "operations/movefile") == 1
    stat_remotes = [
        call.kwargs["remote"]
        for call in rclone.rpc.call_args_list
        if call.args[0] == "operations/stat"
    ]
    assert stat_remotes == ["destination/file.staging", "destination/file"]
    assert fingerprint.call_count == 3


@pytest.mark.parametrize(
    "case",
    ["existing", "missing_stage", "invalid_destination", "source_changed", "stage_changed"],
)
def test_publication_refuses_unsafe_preconditions(monkeypatch, case):
    """Existing destinations, missing stages and changed data are not moved."""
    rclone = mock.Mock()
    rclone.rpc.side_effect = lambda method, **kwargs: (
        {}
        if method == "operations/stat"
        and not kwargs["remote"].endswith("staging")
        and case == "invalid_destination"
        else {
            "item": (
                None
                if kwargs["remote"].endswith("staging") and case == "missing_stage"
                else {"Name": "existing"}
                if kwargs["remote"].endswith("staging") or case == "existing"
                else None
            )
        }
        if method == "operations/stat"
        else {}
    )
    fingerprints = ["changed" if case == "source_changed" else "snapshot"]
    fingerprints.append("changed" if case == "stage_changed" else "snapshot")
    monkeypatch.setattr(rclone_worker, "_content_fingerprint", mock.Mock(side_effect=fingerprints))
    with pytest.raises(ValueError):
        _verify_and_publish(
            rclone,
            {"name": "source", "type": "sftp"},
            {"name": "destination", "type": "s3"},
            "/",
            "/source/file",
            "/",
            "/destination/file",
            "/destination/file.staging",
            "file",
            "snapshot",
        )
    assert not any(call.args[0] == "operations/movefile" for call in rclone.rpc.call_args_list)


def test_publication_reports_changed_published_content(monkeypatch):
    """An unexpected post-move fingerprint must require reconciliation."""
    rclone = mock.Mock()
    rclone.rpc.side_effect = lambda method, **kwargs: (
        {"item": {"Name": "stage"} if kwargs["remote"].endswith("staging") else None}
        if method == "operations/stat"
        else {}
    )
    monkeypatch.setattr(
        rclone_worker,
        "_content_fingerprint",
        mock.Mock(side_effect=["snapshot", "snapshot", "changed"]),
    )
    with pytest.raises(ValueError, match="Published content"):
        _verify_and_publish(
            rclone,
            {"name": "source", "type": "alias"},
            {"name": "destination", "type": "sftp"},
            "/",
            "/source/file",
            "/",
            "/destination/file",
            "/destination/file.staging",
            "file",
            "snapshot",
        )


# pylint: disable=protected-access
def test_real_rclone_stages_and_publishes_file(tmp_path):
    """Exercise staging and best-effort publication against librclone when available."""
    library_path = os.getenv("DLM_RCLONE_LIBRARY_PATH", "/usr/local/lib/librclone.so")
    if not os.path.isfile(library_path):
        pytest.skip("librclone is not installed")
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    source_root.mkdir()
    destination_root.mkdir()
    source_file = source_root / "data.bin"
    source_file.write_bytes(b"staged-data-" * 64)
    source_config = {
        "name": "migration-test-source",
        "type": "alias",
        "parameters": {"remote": str(source_root)},
    }
    destination_config = {
        "name": "migration-test-destination",
        "type": "alias",
        "parameters": {"remote": str(destination_root)},
    }
    rclone = embedded_rclone.Rclone(library_path)
    try:
        rclone.rpc("config/create", **source_config)
        rclone.rpc("config/create", **destination_config)
        fingerprint = rclone_worker._content_fingerprint(
            rclone, f"{source_config['name']}:/data.bin", is_container=False
        )
        execution_id = str(uuid.uuid4())
        job_id, _ = _execute_rclone_copy(
            rclone,
            source_config,
            destination_config,
            f"{source_config['name']}:/",
            "/data.bin",
            "/",
            f"{destination_config['name']}:/",
            "/.data.bin.staging",
            "/",
            "file",
            execution_id,
        )
        deadline = time.monotonic() + 30
        while True:
            status, _ = _poll_rclone_job(rclone, job_id, execution_id)
            if status["finished"]:
                assert status["success"] is True
                break
            if time.monotonic() >= deadline:
                pytest.fail("Rclone staging copy did not finish")
            time.sleep(0.05)

        _verify_and_publish(
            rclone,
            source_config,
            destination_config,
            "/",
            "/data.bin",
            "/",
            "/data.bin",
            "/.data.bin.staging",
            "file",
            fingerprint,
        )
        assert (destination_root / "data.bin").read_bytes() == source_file.read_bytes()
        assert not (destination_root / ".data.bin.staging").exists()
    finally:
        rclone.close()


def test_item_copy_values_rewrites_tree_links():
    """Copied items point at destination UIDs and storage, not source records."""
    source_parent_uid = uuid.uuid4()
    source_uid = uuid.uuid4()
    destination_parent_uid = uuid.uuid4()
    destination_uid = uuid.uuid4()
    destination_storage_id = uuid.uuid4()
    source_item = DataItem(
        UID=source_uid,
        parents=source_parent_uid,
        children=uuid.uuid4(),
        item_state=ItemState.READY,
    )

    values = _item_copy_values(
        source_item,
        destination_uid,
        destination_storage_id,
        PhaseType.SOLID,
        "/destination/item",
        {
            source_parent_uid: destination_parent_uid,
            source_uid: destination_uid,
        },
    )

    assert values["UID"] == destination_uid
    assert values["UID_deletion"] is None
    assert values["storage_id"] == destination_storage_id
    assert values["item_state"] == ItemState.READY
    assert values["parents"] == destination_parent_uid
    assert values["children"] is None
    assert values["uri"] == "/destination/item"


def test_copy_request_builds_file_rpc():
    """Files use copyfile RPC."""
    method, parameters = _copy_request(
        "source:/",
        "/source/file",
        "/",
        "destination:/",
        "/destination/file",
        "/",
        "file",
    )

    assert method == "operations/copyfile"
    assert parameters == {
        "srcFs": "source://",
        "srcRemote": "/source/file",
        "dstFs": "destination:/",
        "dstRemote": "/destination/file",
        "s3-no-check-bucket": True,
    }


def test_copy_request_builds_container_rpc():
    """Container copies preserve their source and destination roots."""
    method, parameters = _copy_request(
        "source:/",
        "/source/container",
        "/",
        "destination:/",
        "/destination/container",
        "/",
        "container",
    )

    assert method == "sync/copy"
    assert parameters == {
        "srcFs": "source:////source/container",
        "dstFs": "destination://destination/container",
        "no-check-dest": True,
        "s3-no-check-bucket": True,
    }


def test_execute_rclone_copy_creates_remotes_and_submits_embedded_async_job():
    """Embedded RPC registers both backends and returns an asynchronous job ID."""

    class FakeRclone:  # pylint: disable=too-few-public-methods
        """Record embedded RPC calls and return test transfer statistics."""

        def __init__(self):
            self.calls = []

        def rpc(self, method, **parameters):
            """Record the call and return a job ID for file copies."""
            self.calls.append((method, parameters))
            if method == "operations/copyfile":
                return {"jobid": 42}
            return {}

    rclone = FakeRclone()
    source_config = {"name": "source", "type": "alias", "parameters": {"remote": "/"}}
    destination_config = {
        "name": "destination",
        "type": "alias",
        "parameters": {"remote": "/"},
    }
    execution_id = str(uuid.uuid4())

    job_id, command = _execute_rclone_copy(
        rclone,
        source_config,
        destination_config,
        "source:/",
        "/source/file",
        "/",
        "destination:/",
        "/destination/file",
        "/",
        "file",
        execution_id,
    )

    assert [call[0] for call in rclone.calls] == [
        "config/create",
        "config/create",
        "operations/copyfile",
    ]
    assert rclone.calls[0][1] == source_config
    assert rclone.calls[1][1] == destination_config
    assert rclone.calls[2][1]["_group"] == execution_id
    assert rclone.calls[2][1]["_async"] is True
    assert job_id == 42
    assert command.startswith("operations/copyfile")


@pytest.mark.parametrize(
    ("status", "expected_calls", "expected_stats"),
    [
        ({"finished": False}, ["job/status"], None),
        (
            {"finished": True, "success": True},
            ["job/status", "core/stats"],
            {"bytes": 15},
        ),
    ],
)
def test_poll_rclone_job_reads_status_and_grouped_stats(status, expected_calls, expected_stats):
    """Polls an embedded job and only loads stats after it finishes."""

    class FakeRclone:  # pylint: disable=too-few-public-methods
        """Return a configured status and grouped stats."""

        def __init__(self):
            self.calls = []

        def rpc(self, method, **parameters):
            """Record the call and return the configured status or stats."""
            self.calls.append((method, parameters))
            return status if method == "job/status" else {"bytes": 15}

    execution_id = str(uuid.uuid4())
    rclone = FakeRclone()

    result_status, stats = _poll_rclone_job(rclone, 42, execution_id)

    assert result_status == status
    assert stats == expected_stats
    assert [call[0] for call in rclone.calls] == expected_calls
    if expected_stats is not None:
        assert rclone.calls[1][1] == {"group": execution_id}


@pytest.mark.asyncio
async def test_copy_rejects_item_with_active_migration_under_for_update_lock():
    # pylint: disable=protected-access
    """A second copy cannot queue while another migration is incomplete."""
    source_item = DataItem(
        UID=uuid.uuid4(),
        storage_id=uuid.uuid4(),
        item_state=ItemState.READY,
    )
    session = _MigrationSession(source_item, active_migration_id=1)

    with pytest.raises(UnmetPreconditionForOperation, match="active migration"):
        await dlm_migration_requests._copy_data_item(
            session,
            uid=str(source_item.UID),
            destination_id=str(uuid.uuid4()),
        )

    assert session.statements[0]._for_update_arg is not None


@pytest.mark.asyncio
async def test_copy_does_not_change_source_item_state():
    # pylint: disable=protected-access
    """Queued copies leave the source state unchanged."""
    source_storage_id = uuid.uuid4()
    destination_storage_id = uuid.uuid4()
    source_item = DataItem(
        UID=uuid.uuid4(),
        storage_id=source_storage_id,
        uri="/source/file",
        item_type="file",
        item_state=ItemState.READY,
    )
    storage_rows = (
        SimpleNamespace(storage_id=source_storage_id, root_directory="/"),
        SimpleNamespace(config_id=1),
        SimpleNamespace(storage_id=destination_storage_id, storage_phase=PhaseType.SOLID),
        SimpleNamespace(config_id=2),
    )
    session = _MigrationSession(source_item, storage_rows=storage_rows)

    await dlm_migration_requests._copy_data_item(
        session,
        uid=str(source_item.UID),
        destination_id=str(destination_storage_id),
        path="/destination/file",
    )

    assert source_item.item_state == ItemState.READY


@pytest.mark.parametrize(
    ("left", "right", "overlap"),
    [
        ("/dir/file", "dir/file", True),
        ("/dir", "/dir/file", True),
        ("/dir/file", "/dir", True),
        ("/dir", "/directory/file", False),
        ("/", "/other", True),
    ],
)
def test_destination_path_overlap(left, right, overlap):
    """Reservations compare normalized path components, not string prefixes."""
    assert dlm_migration_requests._destination_paths_overlap(left, right, "/storage") is overlap


@pytest.mark.asyncio
async def test_recovery_preserves_uncertain_jobs_and_reserved_destination(monkeypatch):
    """Restart does not delete the destination or automatically resubmit an uncertain job."""
    source_uid = uuid.uuid4()
    source_storage_id = uuid.uuid4()
    destination_storage_id = uuid.uuid4()
    stale_execution_id = uuid.uuid4()
    migration = SimpleNamespace(
        migration_id=1,
        complete=False,
        host_id="worker-1",
        job_id=27,
        execution_id=stale_execution_id,
        command="old command",
        job_status={"finished": False},
        job_stats={"bytes": 10},
        uid=source_uid,
        destination_uid=uuid.uuid4(),
        destination_path="/destination/file",
        source_storage_id=source_storage_id,
        destination_storage_id=destination_storage_id,
    )

    class Session:
        """Return configured rows for recovery and migration dispatch."""

        def __init__(self):
            self.scalar_calls = 0
            self.statement = None

        async def __aenter__(self):
            """Enter the fake session context."""
            return self

        async def __aexit__(self, *_exc_info):
            """Leave the fake session context."""
            return False

        def begin(self):
            """Start a fake transaction."""
            return _Transaction()

        async def scalars(self, statement):
            """Return the configured migrations and capture the query."""
            self.statement = statement
            return SimpleNamespace(all=lambda: [migration])

        async def scalar(self, _statement):
            """Return the migration first, then its source item."""
            self.scalar_calls += 1
            return migration if self.scalar_calls == 1 else source_item

        async def execute(self, _statement):
            """Return source/destination storage and Rclone configurations."""
            return SimpleNamespace(
                first=lambda: (
                    SimpleNamespace(root_directory="/"),
                    SimpleNamespace(
                        config={
                            "name": "source",
                            "type": "alias",
                            "parameters": {"remote": "/"},
                        }
                    ),
                    SimpleNamespace(
                        root_directory="/",
                        storage_id=destination_storage_id,
                        storage_phase=PhaseType.SOLID,
                    ),
                    SimpleNamespace(
                        config={
                            "name": "destination",
                            "type": "alias",
                            "parameters": {"remote": "/"},
                        }
                    ),
                )
            )

    class FakeRclone:  # pylint: disable=too-few-public-methods
        """Return an Rclone job ID and capture the asynchronous copy request."""

        def __init__(self):
            self.calls = []

        def rpc(self, method, **parameters):
            """Capture the copy request and provide a job ID."""
            self.calls.append((method, parameters))
            return {"jobid": 1} if method == "operations/copyfile" else {}

    source_item = DataItem(
        UID=source_uid,
        storage_id=source_storage_id,
        uri="/source/file",
        item_type="file",
    )
    recovery_session = Session()
    cleaned = []

    async def cleanup(_session, migration_to_clean, _rclone):
        cleaned.append(migration_to_clean)

    monkeypatch.setattr(rclone_worker, "_cleanup_partial_destination", cleanup)

    assert await _recover_owned_migrations(lambda: recovery_session, object(), "worker-1") == 1

    assert not cleaned
    assert "migration.host_id = :host_id_1" in str(recovery_session.statement)
    assert migration.job_id == 27
    assert migration.execution_id != stale_execution_id
    assert migration.job_status["previous_execution_id"] == str(stale_execution_id)
    assert migration.host_id == "worker-1"
    assert migration.command == "old command"
    assert migration.job_status["reconciliation_required"] is True
    assert migration.job_stats == {"bytes": 10}

    dispatch_session = Session()
    rclone = FakeRclone()
    destination_uid = migration.destination_uid
    assert not await _dispatch_migration(
        lambda: dispatch_session, migration.migration_id, rclone, "worker-1"
    )
    assert migration.destination_uid == destination_uid
    assert not rclone.calls


@pytest.mark.asyncio
async def test_recovery_quarantines_opted_in_s3_migration():
    """A replacement worker cannot assume that the old worker has stopped."""
    worker_state = {
        "staging_path": "/destination/file.stage",
        "source_fingerprint": "source-digest",
        "s3_retry_enabled": True,
        "retry_count": 4,
    }
    migration = SimpleNamespace(
        migration_id=1,
        complete=False,
        host_id="worker-1",
        job_id=27,
        execution_id=uuid.uuid4(),
        command="old command",
        job_status={"finished": False, "_dlm_worker": worker_state},
        job_stats={"bytes": 7},
    )
    previous_execution_id = migration.execution_id

    class Session:
        """Provide the transaction and migration lookup used by recovery."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            """Return a fake database transaction."""
            return _Transaction()

        async def scalars(self, _statement):
            """Return the migration being recovered."""
            return SimpleNamespace(all=lambda: [migration])

    assert await _recover_owned_migrations(Session, object(), "worker-1") == 1
    assert migration.job_id == 27
    assert migration.execution_id != previous_execution_id
    assert migration.job_status["previous_execution_id"] == str(previous_execution_id)
    assert migration.host_id == "worker-1"
    assert migration.job_status["finished"] is False
    assert migration.job_status["reconciliation_required"] is True
    assert migration.job_status["_dlm_worker"] == worker_state


@pytest.mark.asyncio
async def test_cleanup_keeps_unowned_destination_and_reserved_row():
    """A failure cannot delete pre-existing destination data or the reserved UID."""
    migration = SimpleNamespace(
        migration_id=1,
        destination_uid=uuid.uuid4(),
        destination_path="/destination/file",
    )
    session = SimpleNamespace()
    rclone = SimpleNamespace()

    await rclone_worker._cleanup_partial_destination(session, migration, rclone)

    assert migration.destination_uid is not None


@pytest.mark.asyncio
async def test_legacy_job_fails_with_outbox_without_touching_payload(monkeypatch):
    """An ownerless old-daemon job needs operator intervention, not resubmission."""
    migration = SimpleNamespace(
        migration_id=1,
        job_id=27,
        host_id=None,
        execution_id=None,
        uid=None,
        destination_uid=uuid.uuid4(),
        destination_path="/existing",
    )
    events = []

    class Session:
        """Provide the transaction and migration lookup used by legacy handling."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            """Return a fake database transaction."""
            return _Transaction()

        async def scalar(self, _statement):
            """Return the migration record."""
            return migration

    async def record_event(**kwargs):
        events.append(kwargs)

    monkeypatch.setattr(rclone_worker, "add_outbox_event", record_event)
    monkeypatch.setattr(rclone_worker, "_migration_to_dict", lambda item: dict(item.job_status))
    destination_uid = migration.destination_uid
    assert await _dispatch_migration(Session, 1, object(), "worker-1")
    assert migration.complete is True
    assert migration.job_status["success"] is False
    assert "Stop the old daemon" in migration.job_status["error"]
    assert migration.destination_uid == destination_uid
    assert len(events) == 1
    assert events[0]["event_type"] == "dlm.migration.update"


@pytest.mark.asyncio
async def test_poll_error_leaves_job_in_progress(monkeypatch):
    """A temporary polling error must not imply that the external job stopped."""
    migration = SimpleNamespace(
        migration_id=1,
        job_id=27,
        host_id="worker-1",
        execution_id=uuid.uuid4(),
        job_status={"finished": False},
        complete=False,
    )

    class Session:
        """Provide the transaction and migration lookup used by polling."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            """Return a fake database transaction."""
            return _Transaction()

        async def scalar(self, _statement):
            """Return the migration record."""
            return migration

    def fail_poll(*_args):
        raise RuntimeError("RPC unavailable")

    monkeypatch.setattr(rclone_worker, "_poll_rclone_job", fail_poll)
    assert not await _dispatch_migration(Session, 1, object(), "worker-1")
    assert migration.complete is False
    assert migration.job_status == {"finished": False}


@pytest.mark.asyncio
async def test_worker_iteration_rotates_past_long_running_jobs(monkeypatch):
    """A full batch of active jobs must not starve newer queued migrations."""
    dispatched = []

    async def migration_ids(_session_factory, _worker_id, after_id=0):
        return [migration_id for migration_id in range(1, 53) if migration_id > after_id][:50]

    async def dispatch(_session_factory, migration_id, _rclone, _worker_id):
        dispatched.append(migration_id)
        return True

    monkeypatch.setattr(rclone_worker, "_migration_ids", migration_ids)
    monkeypatch.setattr(rclone_worker, "_dispatch_migration", dispatch)

    cursor = await rclone_worker._run_worker_iteration(None, None, "worker-1", 0)
    assert dispatched == list(range(1, 51))
    cursor = await rclone_worker._run_worker_iteration(None, None, "worker-1", cursor)
    assert dispatched[-2:] == [51, 52]
    cursor = await rclone_worker._run_worker_iteration(None, None, "worker-1", cursor)
    assert cursor == 50
    assert dispatched[-50:] == list(range(1, 51))


@pytest.mark.asyncio
async def test_migration_ids_selects_next_batch_from_database():
    """A later queued migration is returned after a full batch of active jobs."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.execute(text("ATTACH DATABASE ':memory:' AS dlm"))
            await connection.execute(
                text(
                    "CREATE TABLE dlm.migration (migration_id INTEGER PRIMARY KEY, "
                    "complete BOOLEAN, job_id INTEGER, execution_id TEXT, host_id TEXT, "
                    "job_status TEXT)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO dlm.migration VALUES "
                    "(:id, 0, :job, :execution, :host, :status)"
                ),
                [
                    {
                        "id": migration_id,
                        "job": migration_id if migration_id <= 50 else None,
                        "execution": "execution" if migration_id <= 50 else None,
                        "host": "worker-1" if migration_id <= 50 else None,
                        "status": '{"finished":false}',
                    }
                    for migration_id in range(1, 53)
                ],
            )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        first = await rclone_worker._migration_ids(factory, "worker-1")
        second = await rclone_worker._migration_ids(factory, "worker-1", first[-1])
        assert first == list(range(1, 51))
        assert second == [51, 52]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_iteration_continues_after_job_error(monkeypatch):
    """One malformed migration must not prevent later jobs from being processed."""
    dispatched = []

    async def migration_ids(_session_factory, _worker_id, _after_id=0):
        return [1, 2]

    async def dispatch(_session_factory, migration_id, _rclone, _worker_id):
        dispatched.append(migration_id)
        if migration_id == 1:
            raise ValueError("invalid migration")
        return True

    monkeypatch.setattr(rclone_worker, "_migration_ids", migration_ids)
    monkeypatch.setattr(rclone_worker, "_dispatch_migration", dispatch)

    assert await rclone_worker._run_worker_iteration(None, None, "worker-1", 0) == 2
    assert dispatched == [1, 2]


@pytest.mark.asyncio
async def test_successful_job_persists_publication_intent_before_publish(monkeypatch):
    """A completed copy is recorded before publication is attempted."""
    worker_state = {
        "staging_path": "/destination/file.stage",
        "source_fingerprint": "source-digest",
        "s3_retry_enabled": False,
    }
    migration = SimpleNamespace(
        migration_id=1,
        job_id=27,
        host_id="worker-1",
        execution_id=uuid.uuid4(),
        job_status={"finished": False, "_dlm_worker": worker_state},
        job_stats=None,
        complete=False,
    )
    finished = []

    class Session:
        """Provide the transaction and migration lookup used by publication."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            """Return a fake database transaction."""
            return _Transaction()

        async def scalar(self, _statement):
            """Return the migration record."""
            return migration

    async def finish(*_args, **_kwargs):
        finished.append(True)

    monkeypatch.setattr(
        rclone_worker,
        "_poll_rclone_job",
        lambda *_args: ({"finished": True, "success": True}, {"bytes": 7}),
    )
    monkeypatch.setattr(rclone_worker, "_finish_migration", finish)
    assert await _dispatch_migration(Session, 1, object(), "worker-1")
    assert migration.job_status["_dlm_worker"]["publication_pending"] is True
    assert not finished

    assert await _dispatch_migration(Session, 1, object(), "worker-1")
    assert finished == [True]


@pytest.mark.asyncio
async def test_publication_error_requires_reconciliation(monkeypatch):
    """A failed publication may have changed remote storage and must not be terminal."""
    source = DataItem(UID=uuid.uuid4(), uri="/source", item_type="file")
    migration = SimpleNamespace(
        migration_id=1,
        destination_storage_id=uuid.uuid4(),
        destination_path="/destination",
        job_status=None,
        job_stats=None,
        complete=False,
        completion_date=None,
    )
    storage = SimpleNamespace(root_directory="/")
    config = SimpleNamespace(config={"name": "remote", "type": "sftp", "parameters": {}})
    events = []

    class Session:  # pylint: disable=too-few-public-methods
        """Return the destination storage."""

        async def scalar(self, _statement):
            """Return the destination storage."""
            return storage

    async def lock_source(*_args):
        return source

    async def load_context(*_args):
        return storage, config, storage, config

    async def add_event(**kwargs):
        events.append(kwargs)

    def fail_publication(*_args):
        raise embedded_rclone.RcloneException({"error": "connection lost during move"}, 500)

    monkeypatch.setattr(rclone_worker, "_lock_source_item", lock_source)
    monkeypatch.setattr(rclone_worker, "_load_copy_context", load_context)
    monkeypatch.setattr(rclone_worker, "_verify_and_publish", fail_publication)
    monkeypatch.setattr(rclone_worker, "add_outbox_event", add_event)
    monkeypatch.setattr(rclone_worker, "_migration_to_dict", lambda item: dict(item.job_status))
    status = {
        "finished": True,
        "success": True,
        "_dlm_worker": {
            "staging_path": "/stage",
            "source_fingerprint": "digest",
            "source_tree_fingerprint": "tree",
        },
    }

    await rclone_worker._finish_migration(Session(), migration, None, status, None, success=True)

    assert migration.complete is False
    assert migration.completion_date is None
    assert migration.job_status["success"] is False
    assert migration.job_status["reconciliation_required"] is True
    assert "connection lost" in migration.job_status["error"]
    assert len(events) == 1


@pytest.mark.asyncio
async def test_changed_source_tree_cannot_be_finalized(monkeypatch):
    """A child change during a copy must not create READY destination records."""
    source = DataItem(UID=uuid.uuid4(), uri="/source", item_type="container")
    migration = SimpleNamespace(
        migration_id=1,
        destination_storage_id=uuid.uuid4(),
        destination_path="/destination",
        job_status=None,
        job_stats=None,
        complete=False,
        completion_date=None,
    )
    storage = SimpleNamespace(root_directory="/")
    config = SimpleNamespace(config={"name": "remote", "type": "sftp", "parameters": {}})
    created = []

    class Session:  # pylint: disable=too-few-public-methods
        """Return the destination storage."""

        async def scalar(self, _statement):
            """Return the destination storage."""
            return storage

    async def lock_source(*_args):
        return source

    async def load_context(*_args):
        return storage, config, storage, config

    async def tree_fingerprint(*_args):
        return "changed"

    async def create_tree(*_args):
        created.append(True)

    async def add_event(**_kwargs):
        pass

    monkeypatch.setattr(rclone_worker, "_lock_source_item", lock_source)
    monkeypatch.setattr(rclone_worker, "_load_copy_context", load_context)
    monkeypatch.setattr(rclone_worker, "_verify_and_publish", lambda *_args: None)
    monkeypatch.setattr(rclone_worker, "_source_tree_fingerprint", tree_fingerprint, raising=False)
    monkeypatch.setattr(rclone_worker, "_create_destination_tree", create_tree)
    monkeypatch.setattr(rclone_worker, "add_outbox_event", add_event)
    monkeypatch.setattr(rclone_worker, "_migration_to_dict", lambda item: dict(item.job_status))
    status = {
        "finished": True,
        "success": True,
        "_dlm_worker": {
            "staging_path": "/stage",
            "source_fingerprint": "bytes",
            "source_tree_fingerprint": "original",
        },
    }

    await rclone_worker._finish_migration(Session(), migration, None, status, None, success=True)

    assert not created
    assert migration.complete is False
    assert migration.job_status["reconciliation_required"] is True
    assert "tree" in migration.job_status["error"].lower()


@pytest.mark.asyncio
async def test_uncertain_submission_keeps_claim_without_failing_job(monkeypatch):
    """A lost submission response must not make a possibly running job retryable."""
    source_uid = uuid.uuid4()
    migration = SimpleNamespace(
        migration_id=1,
        job_id=None,
        host_id=None,
        execution_id=None,
        job_status=None,
        uid=source_uid,
        destination_uid=uuid.uuid4(),
        destination_path="/destination",
        source_storage_id=uuid.uuid4(),
        destination_storage_id=uuid.uuid4(),
        complete=False,
    )
    source = DataItem(UID=source_uid, uri="/source", item_type="file")

    class Session:
        """Provide the transaction and config lookup used by dispatch."""

        def __init__(self):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            """Return a fake database transaction."""
            return _Transaction()

        async def scalar(self, _statement):
            """Return the migration, then its source item."""
            self.calls += 1
            return migration if self.calls == 1 else source

        async def execute(self, _statement):
            """Return matching source and destination storage configurations."""
            config = {"name": "storage", "type": "alias", "parameters": {"remote": "/"}}
            return SimpleNamespace(
                first=lambda: (
                    SimpleNamespace(root_directory="/"),
                    SimpleNamespace(config=config),
                    SimpleNamespace(root_directory="/"),
                    SimpleNamespace(config=config),
                )
            )

    class FakeRclone:  # pylint: disable=too-few-public-methods
        """Simulate staging setup before a lost submission response."""

        def rpc(self, method, **_parameters):
            """Return empty stage information and a deterministic hash."""
            if method == "operations/stat":
                assert not _parameters["remote"].startswith("/")
                return {"item": None}
            if method == "operations/hashsum":
                return {"hashsum": ["sha256  file"]}
            return {}

    def fail_submission(*_args):
        raise RuntimeError("response lost")

    async def fingerprint_tree(*_args):
        return "tree"

    monkeypatch.setattr(rclone_worker, "_source_tree_fingerprint", fingerprint_tree)
    monkeypatch.setattr(rclone_worker, "_execute_rclone_copy", fail_submission)
    assert await _dispatch_migration(Session, 1, FakeRclone(), "worker-1")
    assert migration.complete is False
    assert migration.host_id == "worker-1"
    assert migration.execution_id is not None
    assert migration.job_status["finished"] is False
    assert migration.job_status["reconciliation_required"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_claim_commit", [False, True])
async def test_copy_submission_waits_for_claim_commit(  # noqa: C901
    monkeypatch, fail_claim_commit
):
    """A claim commit failure must not start an untracked external copy."""
    source_uid = uuid.uuid4()
    migration = SimpleNamespace(
        migration_id=1,
        job_id=None,
        host_id=None,
        execution_id=None,
        job_status=None,
        uid=source_uid,
        destination_uid=uuid.uuid4(),
        destination_path="/destination",
        source_storage_id=uuid.uuid4(),
        destination_storage_id=uuid.uuid4(),
        complete=False,
        command=None,
    )
    source = DataItem(UID=source_uid, uri="/source", item_type="file")
    events = []

    class Transaction:
        """Track whether the initial database transaction was committed."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            if not events and fail_claim_commit:
                raise RuntimeError("claim commit failed")
            events.append("commit")
            return False

    class Session:
        """Supply the migration and source rows for each transaction."""

        def __init__(self):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            """Begin a fake transaction."""
            return Transaction()

        async def scalar(self, _statement):
            """Return the migration or source item."""
            self.calls += 1
            return migration if self.calls == 1 else source

        async def execute(self, _statement):
            """Return fake source and destination storage configurations."""
            config = {"name": "storage", "type": "alias", "parameters": {"remote": "/"}}
            return SimpleNamespace(
                first=lambda: (
                    SimpleNamespace(root_directory="/"),
                    SimpleNamespace(config=config),
                    SimpleNamespace(root_directory="/"),
                    SimpleNamespace(config=config),
                )
            )

    class FakeRclone:  # pylint: disable=too-few-public-methods
        """Supply empty staging and deterministic source fingerprint results."""

        def rpc(self, method, **_parameters):
            """Return deterministic stat and hash results."""
            if method == "operations/stat":
                return {"item": None}
            if method == "operations/hashsum":
                return {"hashsum": ["sha256  file"]}
            return {}

    def submit(*_args):
        assert events == ["commit"]
        assert migration.job_status["reconciliation_required"] is True
        events.append("submit")
        return 42, "copy command"

    async def fingerprint_tree(*_args):
        return "tree"

    monkeypatch.setattr(rclone_worker, "_source_tree_fingerprint", fingerprint_tree)
    monkeypatch.setattr(rclone_worker, "_execute_rclone_copy", submit)
    if fail_claim_commit:
        with pytest.raises(RuntimeError, match="claim commit failed"):
            await _dispatch_migration(Session, 1, FakeRclone(), "worker-1")
        assert not events
    else:
        assert await _dispatch_migration(Session, 1, FakeRclone(), "worker-1")
        assert events == ["commit", "submit", "commit"]
        assert migration.job_id == 42
        assert migration.job_status["finished"] is False
        assert "reconciliation_required" not in migration.job_status


@pytest.mark.asyncio
# pylint: disable=protected-access
async def test_remote_retry_reuses_staging_path(monkeypatch):
    """A remote migration retries against its stable staging key."""
    source_uid = uuid.uuid4()
    migration = SimpleNamespace(
        migration_id=1,
        uid=source_uid,
        source_storage_id=uuid.uuid4(),
        destination_storage_id=uuid.uuid4(),
        job_id=27,
        execution_id=uuid.uuid4(),
        host_id="worker-1",
        command="old command",
        job_stats=None,
        job_status=None,
    )
    source = DataItem(UID=source_uid, uri="/source/file", item_type="file")
    source_storage = SimpleNamespace(root_directory="/")
    destination_storage = SimpleNamespace(root_directory="/")
    source_config = SimpleNamespace(config={"name": "source", "type": "alias", "parameters": {}})
    destination_config = SimpleNamespace(
        config={"name": "destination", "type": "s3", "parameters": {"leave_parts_on_error": True}}
    )
    rows = (source_storage, source_config, destination_storage, destination_config)

    class Session:  # pylint: disable=too-few-public-methods
        """Provide the transaction and migration lookup used by retry."""

        async def scalar(self, _statement):
            """Return the source item."""
            return source

    async def load_context(_session, _migration):
        return rows

    monkeypatch.setattr(rclone_worker, "_load_copy_context", load_context)
    monkeypatch.setattr(rclone_worker, "_content_fingerprint", lambda *_args, **_kwargs: "same")
    worker_state = {
        "staging_path": "/destination/file.staging",
        "source_fingerprint": "same",
        "retry_enabled": True,
        "retry_count": 3,
    }

    submission = await rclone_worker._prepare_remote_retry(
        Session(), migration, object(), "worker-1", worker_state
    )
    assert submission is not None
    execution_id, copy_arguments = submission
    assert copy_arguments[6] == "/destination/file.staging"
    assert migration.job_id is None
    assert migration.execution_id == execution_id
    assert str(execution_id) == copy_arguments[-1]
    assert migration.job_status["reconciliation_required"] is True
    assert migration.job_status["_dlm_worker"]["retry_count"] == 4
    assert migration.job_status["_dlm_worker"]["staging_path"] == worker_state["staging_path"]


@pytest.mark.asyncio
async def test_s3_failure_stops_after_five_copy_attempts(monkeypatch):
    """A permanently failing S3 copy must eventually finish rather than retry forever."""
    worker_state = {"s3_retry_enabled": True, "retry_count": 4}
    migration = SimpleNamespace(
        job_id=27,
        execution_id=uuid.uuid4(),
        job_status={"finished": False, "_dlm_worker": worker_state},
        job_stats=None,
    )
    finished = []
    retries = []

    async def retry(*_args):
        retries.append(True)
        return True

    async def finish(_session, _migration, _rclone, status, _stats, *, success):
        finished.append((status, success))

    monkeypatch.setattr(
        rclone_worker,
        "_poll_rclone_job",
        lambda *_args: ({"finished": True, "success": False, "error": "access denied"}, None),
    )
    monkeypatch.setattr(rclone_worker, "_prepare_remote_retry", retry, raising=False)
    monkeypatch.setattr(rclone_worker, "_finish_migration", finish)

    assert await rclone_worker._dispatch_active_job(None, migration, None, "worker-1", 1)
    assert not retries
    assert len(finished) == 1
    assert finished[0][1] is False
    assert "five" in finished[0][0]["error"].lower()
    assert "access denied" in finished[0][0]["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        'request send failed, Head "http://localhost/bucket/key": '
        "dial tcp 127.0.0.1:57831: connect: connection refused",
        "NewFs: couldn't connect SSH: dial tcp 127.0.0.1:57832: connect: connection refused",
    ],
)
async def test_connection_refused_is_retryable_even_when_stats_say_false(monkeypatch, error):
    """Rclone reports retryError=false for observed S3 and SFTP connection refusals."""
    migration = SimpleNamespace(
        job_id=27,
        execution_id=uuid.uuid4(),
        job_status={"finished": False, "_dlm_worker": {"retry_enabled": True, "retry_count": 0}},
        job_stats=None,
    )
    monkeypatch.setattr(
        rclone_worker,
        "_poll_rclone_job",
        lambda *_args: (
            {"finished": True, "success": False, "error": error},
            {"retryError": False, "fatalError": False},
        ),
    )
    assert await rclone_worker._dispatch_active_job(None, migration, None, "worker", 1) is True
    assert datetime.fromisoformat(
        migration.job_status["_dlm_worker"]["retry_after"]
    ) > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_remote_retry_waits_for_persisted_backoff(monkeypatch):
    """Retryable SFTP failures must wait for a persisted backoff before resubmission."""
    migration = SimpleNamespace(
        job_id=27,
        execution_id=uuid.uuid4(),
        job_status={"finished": False, "_dlm_worker": {"retry_enabled": True, "retry_count": 0}},
        job_stats=None,
    )
    retries = []
    execution_id = uuid.uuid4()

    async def retry(*_args):
        retries.append(True)
        return execution_id, ()

    monkeypatch.setattr(
        rclone_worker,
        "_poll_rclone_job",
        lambda *_args: (
            {"finished": True, "success": False, "error": "connection reset"},
            {"retryError": True, "fatalError": False},
        ),
    )
    monkeypatch.setattr(rclone_worker, "_prepare_remote_retry", retry, raising=False)

    assert await rclone_worker._dispatch_active_job(None, migration, None, "worker-1", 1) is True
    deadline = datetime.fromisoformat(migration.job_status["_dlm_worker"]["retry_after"])
    assert deadline > datetime.now(timezone.utc)
    assert not retries

    migration.job_status["_dlm_worker"]["retry_after"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    assert await rclone_worker._dispatch_active_job(None, migration, None, "worker-1", 1) == (
        execution_id,
        (),
    )
    assert retries == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stats",
    [
        {"retryError": False, "fatalError": False},
        {"retryError": True, "fatalError": True},
    ],
)
async def test_remote_permanent_failure_is_not_retried(monkeypatch, stats):
    """Rclone-reported permanent or fatal errors must not be retried."""
    migration = SimpleNamespace(
        job_id=27,
        execution_id=uuid.uuid4(),
        job_status={"finished": False, "_dlm_worker": {"retry_enabled": True, "retry_count": 0}},
        job_stats=None,
    )
    finished = []

    async def finish(_session, _migration, _rclone, _status, _stats, *, success):
        finished.append(success)

    monkeypatch.setattr(
        rclone_worker,
        "_poll_rclone_job",
        lambda *_args: ({"finished": True, "success": False, "error": "failed"}, stats),
    )
    monkeypatch.setattr(rclone_worker, "_finish_migration", finish)
    assert await rclone_worker._dispatch_active_job(None, migration, None, "worker-1", 1) is True
    assert finished == [False]


@pytest.mark.asyncio
async def test_remote_failure_without_retry_classification_is_quarantined(monkeypatch):
    """A missing error classification must not trigger an unsafe retry."""
    migration = SimpleNamespace(
        job_id=27,
        execution_id=uuid.uuid4(),
        job_status={"finished": False, "_dlm_worker": {"retry_enabled": True, "retry_count": 0}},
        job_stats=None,
    )
    events = []

    async def record_event(**kwargs):
        events.append(kwargs)

    monkeypatch.setattr(
        rclone_worker,
        "_poll_rclone_job",
        lambda *_args: ({"finished": True, "success": False, "error": "failed"}, None),
    )
    monkeypatch.setattr(rclone_worker, "add_outbox_event", record_event)
    monkeypatch.setattr(rclone_worker, "_migration_to_dict", lambda item: dict(item.job_status))
    assert await rclone_worker._dispatch_active_job(None, migration, None, "worker-1", 1) is True
    assert migration.job_status["reconciliation_required"] is True
    assert len(events) == 1
