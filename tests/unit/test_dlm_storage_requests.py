# pylint: disable=C0116
# pylint: disable=R0903
# pylint: disable=W0613
"""Storage requests tests."""
import types

from ska_dlm.dlm_storage import dlm_storage_requests as ds


class _MockResp:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_rclone_access_success_no_config(monkeypatch):
    """rclone_access returns True and the item payload when the remote responds 200."""
    urls = ["http://rclone-server.local"]
    monkeypatch.setattr(ds, "CONFIG", types.SimpleNamespace(RCLONE=urls))

    recorded = {}

    def fake_post(url, post_data=None, timeout=None, verify=None):
        # record values for assertions
        recorded["url"] = url
        recorded["post_data"] = post_data
        recorded["timeout"] = timeout
        recorded["verify"] = verify
        return _MockResp(200, {"item": {"name": "myvolume"}})

    monkeypatch.setattr(ds.requests, "post", fake_post)

    result, item = ds.rclone_access(volume="myvolume")

    assert result is True
    assert item == {"name": "myvolume"}
    assert recorded["url"].endswith("/operations/stat")
    # the helper posts fs/remote and enables s3 bucket check bypass
    assert recorded["post_data"] == {
        "fs": "myvolume",
        "remote": "",
        "s3-no-check-bucket": True,
    }
    assert recorded["timeout"] == 1
    assert recorded["verify"] is False


def test_rclone_access_failure_logs_warning(monkeypatch, caplog):
    """rclone_access returns False and logs when the remote returns non-200."""
    urls = ["http://rclone-server.local"]
    monkeypatch.setattr(ds, "CONFIG", types.SimpleNamespace(RCLONE=urls))

    def fake_post(url, post_data=None, timeout=None, verify=None):
        return _MockResp(500, {"error": "boom"})

    monkeypatch.setattr(ds.requests, "post", fake_post)

    with caplog.at_level("WARNING"):
        result, _ = ds.rclone_access(volume="vol")

    assert result is False
    # ensure a warning message was logged indicating inability to access the remote
    assert any("rclone can not access" in rec.message for rec in caplog.records)


def test_rclone_about_success(monkeypatch):
    """rclone_about posts the endpoint filesystem and returns its response."""
    monkeypatch.setattr(ds, "CONFIG", types.SimpleNamespace(RCLONE=["http://rclone-server.local"]))
    recorded = {}

    def fake_post(url, post_data=None, timeout=None, verify=None):
        recorded.update(url=url, post_data=post_data, timeout=timeout, verify=verify)
        return _MockResp(200, {"total": 100, "used": 25, "objects": 4})

    monkeypatch.setattr(ds.requests, "post", fake_post)

    result = ds.rclone_about("myvolume:/")

    assert result == {"total": 100, "used": 25, "objects": 4}
    assert recorded == {
        "url": "http://rclone-server.local/operations/about",
        "post_data": {"fs": "myvolume:/"},
        "timeout": 10,
        "verify": False,
    }
