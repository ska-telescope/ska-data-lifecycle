"""Tests for Rclone migration-worker helpers."""

import os
import time
import uuid
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
