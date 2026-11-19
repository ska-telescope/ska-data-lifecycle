"""Tests for Rclone migration-worker helpers."""

import uuid
from types import SimpleNamespace

import pytest

from ska_dlm import embedded_rclone
from ska_dlm.common_types import ItemState, PhaseType
from ska_dlm.dlm_db import DataItem
from ska_dlm.dlm_migration import dlm_migration_requests
from ska_dlm.dlm_migration import rclone_worker
from ska_dlm.dlm_migration.rclone_worker import (
    _copy_request,
    _destination_uri,
    _dispatch_migration,
    _execute_rclone_copy,
    _item_copy_values,
    _poll_rclone_job,
    _recover_owned_migrations,
    _storage_remote_path,
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

    class FakeRclone:
        """Record embedded RPC calls and return test transfer statistics."""

        def __init__(self):
            self.calls = []

        def rpc(self, method, **parameters):
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

    class FakeRclone:
        """Return a configured status and grouped stats."""

        def __init__(self):
            self.calls = []

        def rpc(self, method, **parameters):
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

    class FakeFunction:
        """Callable with the attributes ctypes uses for function signatures."""

        def __init__(self, callback):
            self.callback = callback
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.callback(*args)

    class FakeLibrary:
        """Provide the exported librclone functions."""

        def __init__(self):
            self.RcloneRPC = FakeFunction(self.rpc)
            self.RcloneFreeString = FakeFunction(lambda value: calls.append(("free", value)))
            self.RcloneInitialize = FakeFunction(lambda: calls.append(("initialize",)))
            self.RcloneFinalize = FakeFunction(lambda: calls.append(("finalize",)))

        @staticmethod
        def rpc(_method, _parameters):
            response = embedded_rclone._RcloneRPCResult()
            body = b'{"error":"bad request"}' if status_code != 200 else b'{"ok":true}'
            response.Output = embedded_rclone._RcloneRPCString(body)
            response.Status = status_code
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
async def test_recovery_cleans_and_resubmits_with_fresh_rclone_identifiers(monkeypatch):
    """Recovered migrations are submitted again with process-local Rclone IDs."""
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

    class FakeRclone:
        """Return an Rclone job ID and capture the asynchronous copy request."""

        def __init__(self):
            self.calls = []

        def rpc(self, method, **parameters):
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

    assert (
        await _recover_owned_migrations(lambda: recovery_session, object(), "worker-1") == 1
    )

    assert cleaned == [migration]
    assert "migration.host_id = :host_id_1" in str(recovery_session.statement)
    assert migration.job_id is None
    assert migration.execution_id is None
    assert migration.host_id is None
    assert migration.command is None
    assert migration.job_status is None
    assert migration.job_stats is None

    dispatch_session = Session()
    rclone = FakeRclone()
    assert await _dispatch_migration(
        lambda: dispatch_session, migration.migration_id, rclone, "worker-1"
    )

    assert migration.job_id == 1
    assert migration.execution_id != stale_execution_id
    assert migration.host_id == "worker-1"
    assert rclone.calls[-1][0] == "operations/copyfile"
    assert rclone.calls[-1][1]["_group"] == str(migration.execution_id)
    assert rclone.calls[-1][1]["_async"] is True
