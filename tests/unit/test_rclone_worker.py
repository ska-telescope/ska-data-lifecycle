"""Tests for Rclone migration-worker helpers."""

# pylint: disable=too-many-lines

import os
import time
import uuid
from types import SimpleNamespace

import pytest

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
    _s3_retry_enabled,
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
    ("config", "expected"),
    [
        ({"type": "s3", "parameters": {"leave_parts_on_error": True}}, True),
        ({"type": "s3", "parameters": {"leave_parts_on_error": False}}, False),
        ({"type": "sftp", "parameters": {"leave_parts_on_error": True}}, False),
        ({"type": "s3", "parameters": {"leave_parts_on_error": "true"}}, False),
    ],
)
def test_s3_retry_requires_explicit_boolean_opt_in(config, expected):
    """Only explicit S3 configuration enables automatic retries."""
    assert _s3_retry_enabled(config) is expected


# pylint: disable=protected-access
def test_verify_and_publish_moves_only_verified_content_to_absent_destination():
    """Publication compares downloaded bytes and refuses to replace existing paths."""

    class FakeRclone:  # pylint: disable=too-few-public-methods
        """Return deterministic stat and hash results for publication tests."""

        def __init__(self, destination_exists=False):
            self.calls = []
            self.destination_exists = destination_exists

        def rpc(self, method, **parameters):
            """Record calls and simulate the source and destination."""
            self.calls.append((method, parameters))
            if method == "operations/hashsum":
                return {"hashsum": ["sha256  ignored-name"]}
            if method == "operations/stat":
                if parameters["remote"].endswith("staging"):
                    return {"item": {"Name": "staging"}}
                return (
                    {"item": {"Name": "existing"}} if self.destination_exists else {"item": None}
                )
            return {}

    source_config = {"name": "source", "type": "alias", "parameters": {}}
    destination_config = {"name": "destination", "type": "alias", "parameters": {}}
    fingerprint = rclone_worker._content_fingerprint(
        FakeRclone(), "source:/source/file", is_container=False
    )
    rclone = FakeRclone()

    _verify_and_publish(
        rclone,
        source_config,
        destination_config,
        "/",
        "/source/file",
        "/",
        "/destination/file",
        "/destination/file.staging",
        "file",
        fingerprint,
    )

    assert [call[0] for call in rclone.calls].count("operations/hashsum") == 2
    assert rclone.calls[-1][0] == "operations/movefile"

    rclone = FakeRclone(destination_exists=True)
    with pytest.raises(ValueError, match="overwrite is not supported"):
        _verify_and_publish(
            rclone,
            source_config,
            destination_config,
            "/",
            "/source/file",
            "/",
            "/destination/file",
            "/destination/file.staging",
            "file",
            fingerprint,
        )
    assert "operations/movefile" not in [call[0] for call in rclone.calls]


# pylint: disable=protected-access
def test_real_rclone_stages_verifies_and_publishes_file(tmp_path):
    """Exercise the migration RPC sequence against librclone when available."""
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


def test_rclone_config_maps_default_container_key(monkeypatch):
    """Legacy backend config uses the key mounted on the service's shared volume."""
    config = {
        "name": "archive",
        "type": "sftp",
        "parameters": {"key_file": "/root/.ssh/id_rsa", "host": "archive"},
    }
    monkeypatch.setenv("DLM_RCLONE_SSH_KEY_PATH", "/dlm/.ssh/id_rsa")
    monkeypatch.setattr(embedded_rclone.os.path, "isfile", lambda _path: True)

    worker_config = embedded_rclone.rclone_config_for_process(config)

    assert worker_config["parameters"] == {
        "key_file": "/dlm/.ssh/id_rsa",
        "host": "archive",
    }
    assert config["parameters"]["key_file"] == "/root/.ssh/id_rsa"


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


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [(200, None), (400, "bad request")],
)
def test_embedded_rclone_binding_frees_rpc_response(monkeypatch, status_code, expected_error):
    """The ctypes wrapper frees every librclone response, including RPC errors."""
    calls = []

    class FakeFunction:  # pylint: disable=too-few-public-methods
        """Callable with the attributes ctypes uses for function signatures."""

        def __init__(self, callback):
            self.callback = callback
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.callback(*args)

    class FakeLibrary:  # pylint: disable=too-few-public-methods
        """Provide the exported librclone functions."""

        def __init__(self):
            # pylint: disable-next=invalid-name
            self.RcloneRPC = FakeFunction(self.rpc)
            # pylint: disable-next=invalid-name
            self.RcloneFreeString = FakeFunction(lambda value: calls.append(("free", value)))
            # pylint: disable-next=invalid-name
            self.RcloneInitialize = FakeFunction(lambda: calls.append(("initialize",)))
            # pylint: disable-next=invalid-name
            self.RcloneFinalize = FakeFunction(lambda: calls.append(("finalize",)))

        @staticmethod
        def rpc(_method, _parameters):
            """Return a populated ctypes response structure."""
            # pylint: disable=protected-access
            response = embedded_rclone._RcloneRPCResult()
            body = b'{"error":"bad request"}' if status_code != 200 else b'{"ok":true}'
            setattr(response, "Output", embedded_rclone._RcloneRPCString(body))
            setattr(response, "Status", status_code)
            return response

    library = FakeLibrary()
    monkeypatch.setattr(embedded_rclone, "CDLL", lambda _path: library)
    rclone = embedded_rclone.Rclone("unused")

    if expected_error is None:
        assert rclone.rpc("rc/noop") == {"ok": True}
    else:
        with pytest.raises(embedded_rclone.RcloneException, match=expected_error):
            rclone.rpc("rc/noop")
    assert calls[0] == ("initialize",)
    assert calls[1][0] == "free"
    rclone.close()
    assert calls[-1] == ("finalize",)


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
    assert migration.execution_id == stale_execution_id
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
async def test_recovery_requeues_opted_in_s3_migration_with_same_stage():
    """Worker restart keeps S3 retry intent and clears only process-local job IDs."""
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
    assert migration.job_id is None
    assert migration.execution_id is None
    assert migration.host_id is None
    assert migration.job_status["finished"] is False
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
                return {"item": None}
            if method == "operations/hashsum":
                return {"hashsum": ["sha256  file"]}
            return {}

    def fail_submission(*_args):
        raise RuntimeError("response lost")

    monkeypatch.setattr(rclone_worker, "_execute_rclone_copy", fail_submission)
    assert await _dispatch_migration(Session, 1, FakeRclone(), "worker-1")
    assert migration.complete is False
    assert migration.host_id == "worker-1"
    assert migration.execution_id is not None
    assert migration.job_status["finished"] is False
    assert migration.job_status["reconciliation_required"] is True


@pytest.mark.asyncio
# pylint: disable=protected-access
async def test_s3_retry_reuses_staging_path_without_attempt_limit(monkeypatch):
    """An opted-in S3 migration continues retrying against its stable staging key."""
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
    submitted = []

    class Session:  # pylint: disable=too-few-public-methods
        """Provide the transaction and migration lookup used by retry."""

        async def scalar(self, _statement):
            """Return the source item."""
            return source

    async def load_context(_session, _migration):
        return rows

    def submit(*args):
        submitted.append(args)
        return 42, "copy command"

    monkeypatch.setattr(rclone_worker, "_load_copy_context", load_context)
    monkeypatch.setattr(rclone_worker, "_content_fingerprint", lambda *_args, **_kwargs: "same")
    monkeypatch.setattr(rclone_worker, "_execute_rclone_copy", submit)
    worker_state = {
        "staging_path": "/destination/file.staging",
        "source_fingerprint": "same",
        "s3_retry_enabled": True,
        "retry_count": 50,
    }

    assert await rclone_worker._submit_s3_retry(
        Session(), migration, object(), "worker-1", worker_state
    )

    assert submitted[0][7] == "/destination/file.staging"
    assert migration.job_id == 42
    assert str(migration.execution_id) == submitted[0][-1]
    assert migration.job_status["_dlm_worker"]["retry_count"] == 51
    assert migration.job_status["_dlm_worker"]["staging_path"] == worker_state["staging_path"]
