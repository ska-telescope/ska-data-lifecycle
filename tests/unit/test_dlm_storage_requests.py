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


def test_rclone_remote_check_success_no_config(monkeypatch):
    """rclone_remote_check returns True when remote /about responds 200."""
    urls = ["http://rclone-server.local"]
    monkeypatch.setattr(ds, "CONFIG", types.SimpleNamespace(RCLONE=urls))

    recorded = {}

    def fake_post(url, post_data=None, timeout=None, verify=None):
        # record values for assertions
        recorded["url"] = url
        recorded["post_data"] = post_data
        recorded["timeout"] = timeout
        recorded["verify"] = verify
        return _MockResp(200, {"status": "ok"})

    monkeypatch.setattr(ds.requests, "post", fake_post)

    result = ds.rclone_remote_check("myvolume")

    assert result is True
    assert recorded["url"].endswith("/operations/about")
    # when no config is provided, the helper posts {'fs': volume}
    assert recorded["post_data"] == {"fs": "myvolume"}
    assert recorded["timeout"] == 10
    assert recorded["verify"] is False


def test_rclone_remote_check_failure_logs_warning(monkeypatch, caplog):
    """rclone_remote_check returns False and logs when remote returns non-200."""
    urls = ["http://rclone-server.local"]
    monkeypatch.setattr(ds, "CONFIG", types.SimpleNamespace(RCLONE=urls))

    def fake_post(url, post_data=None, timeout=None, verify=None):
        return _MockResp(500, {"error": "boom"})

    monkeypatch.setattr(ds.requests, "post", fake_post)

    with caplog.at_level("WARNING"):
        result = ds.rclone_remote_check("vol", config=None)

    assert result is False
    # ensure a warning message was logged indicating inability to reach
    assert any("rclone can not reach" in rec.message for rec in caplog.records)
