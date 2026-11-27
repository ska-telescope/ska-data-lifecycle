"""Tests for migration worker publication and durable submission."""

# pylint: disable=protected-access

import uuid
from types import SimpleNamespace

import pytest

from ska_dlm import embedded_rclone
from ska_dlm.dlm_db import DataItem
from ska_dlm.dlm_migration import rclone_worker
from ska_dlm.dlm_migration.rclone_worker import _dispatch_migration


class _Transaction:
    """Minimal async transaction context manager."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc_info):
        return False


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
