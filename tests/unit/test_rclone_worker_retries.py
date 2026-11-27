"""Tests for migration worker retry scheduling and classification."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from ska_dlm.dlm_db import DataItem
from ska_dlm.dlm_migration import rclone_worker

# pylint: disable=protected-access


@pytest.mark.asyncio
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
