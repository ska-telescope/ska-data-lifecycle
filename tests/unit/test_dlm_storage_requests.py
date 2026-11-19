# pylint: disable=C0116
"""Storage requests tests."""

import pytest

from ska_dlm.dlm_storage import dlm_storage_requests as ds


def test_get_storage_endpoints_returns_models(monkeypatch):
    """Storage endpoints are returned as validated Pydantic models."""
    monkeypatch.setattr(
        ds.DB,
        "select",
        lambda table, params: [{"storage_id": "storage-1", "storage_name": "archive"}],
    )

    result = ds.get_storage_endpoints()

    assert result == [ds.StorageEndpoint(storage_id="storage-1", storage_name="archive")]


def test_get_storage_config_without_storage_filters_by_config_type(monkeypatch):
    """Unscoped config lookup excludes non-Rclone entries."""
    calls = []
    monkeypatch.setattr(
        ds.DB,
        "select",
        lambda table, params: calls.append((table, params)) or [{"config": {"name": "myvolume"}}],
    )

    assert ds.get_storage_config() == [{"name": "myvolume"}]
    assert calls[0][1]["config_type"] == "eq.rclone"


class _FakeRclone:
    """Record embedded Rclone calls and provide configured responses."""

    def __init__(self, responses=None, error=None):
        self.responses = responses or {}
        self.error = error
        self.calls = []
        self.closed = False

    def rpc(self, method, **parameters):
        self.calls.append((method, parameters))
        if method == self.error:
            raise ds.RcloneException({"error": "backend unavailable"}, 500)
        return self.responses.get(method, {})

    def close(self):
        self.closed = True


def _configure_backend(monkeypatch, config=None):
    """Provide one database-backed backend config to a test."""
    backend_config = config or {
        "name": "myvolume",
        "type": "alias",
        "root_path": "/",
        "parameters": {"remote": "/"},
    }
    monkeypatch.setattr(ds, "get_storage_config", lambda: [backend_config])
    monkeypatch.setattr(ds, "rclone_config_for_process", lambda value: value)
    return backend_config


def test_rclone_access_loads_config_from_database(monkeypatch):
    """Embedded access checks register the DB config and return stat data."""
    config = _configure_backend(monkeypatch)
    rclone = _FakeRclone({"operations/stat": {"item": {"name": "myvolume"}}})
    monkeypatch.setattr(ds, "Rclone", lambda: rclone)

    result, item = ds.rclone_access(volume="myvolume:/")

    assert result is True
    assert item == {"name": "myvolume"}
    assert rclone.calls == [
        ("config/create", config),
        (
            "operations/stat",
            {"fs": "myvolume:/", "remote": "", "s3-no-check-bucket": True},
        ),
    ]
    assert rclone.closed


def test_rclone_access_failure_logs_warning(monkeypatch, caplog):
    """An embedded Rclone backend error produces a logged inaccessible result."""
    _configure_backend(monkeypatch)
    rclone = _FakeRclone(error="operations/stat")
    monkeypatch.setattr(ds, "Rclone", lambda: rclone)

    with caplog.at_level("WARNING"):
        result, item = ds.rclone_access(volume="myvolume:/")

    assert result is False
    assert item is None
    assert any("Rclone cannot access" in rec.message for rec in caplog.records)
    assert rclone.closed


def test_rclone_about_uses_database_config(monkeypatch):
    """Usage queries use an embedded backend loaded from the database."""
    config = _configure_backend(monkeypatch)
    rclone = _FakeRclone({"operations/about": {"total": 100, "used": 25, "objects": 4}})
    monkeypatch.setattr(ds, "Rclone", lambda: rclone)

    result = ds.rclone_about("myvolume:/")

    assert result == {"total": 100, "used": 25, "objects": 4}
    assert rclone.calls == [
        ("config/create", config),
        ("operations/about", {"fs": "myvolume:/"}),
    ]
    assert rclone.closed


@pytest.mark.parametrize(
    ("item_type", "expected_method"),
    [("file", "operations/deletefile"), ("container", "operations/purge")],
)
def test_rclone_delete_uses_embedded_operation(monkeypatch, item_type, expected_method):
    """File and container deletion dispatch to their matching Rclone RPC."""
    monkeypatch.setattr(ds, "rclone_access", lambda *_args, **_kwargs: (True, {}))
    calls = []
    monkeypatch.setattr(
        ds,
        "_rclone_rpc",
        lambda volume, method, **params: calls.append((volume, method, params)),
    )

    assert ds.rclone_delete("myvolume:/", "/path", item_type) is True
    assert calls == [("myvolume:/", expected_method, {"fs": "myvolume:/", "remote": "/path"})]


def test_create_storage_config_only_persists_database_record(monkeypatch):
    """Saving a storage config no longer pushes it to the Rclone RC server."""
    calls = []
    monkeypatch.setattr(
        ds.DB,
        "insert",
        lambda table, json: calls.append((table, json)) or [{"config_id": "config-1"}],
    )

    config_id = ds.create_storage_config(
        storage_id="storage-1",
        config={"name": "myvolume", "type": "alias", "parameters": {"remote": "/"}},
    )

    assert config_id == "config-1"
    assert calls[0][0] == ds.CONFIG.DLM.storage_config_table
