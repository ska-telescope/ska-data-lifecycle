"""Tests for the embedded Rclone binding and configuration."""

import pytest

from ska_dlm import embedded_rclone


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
