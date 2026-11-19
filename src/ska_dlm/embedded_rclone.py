"""Python ctypes binding for the Rclone librclone C API."""

import json
import os
from ctypes import CDLL, Structure, c_char_p, c_int
from typing import Any


class _RcloneRPCString(c_char_p):  # pylint: disable=too-few-public-methods
    """Keep the original C pointer so it can be freed by librclone."""


class _RcloneRPCResult(Structure):  # pylint: disable=too-few-public-methods
    """Result structure returned by RcloneRPC."""

    _fields_ = [("Output", _RcloneRPCString), ("Status", c_int)]


class RcloneException(RuntimeError):
    """An error returned by an embedded Rclone RPC call."""

    def __init__(self, output: dict[str, Any], status: int):
        self.output = output
        self.status = status
        super().__init__(output.get("error", "Unknown Rclone error"))


def rclone_config_for_process(config: dict) -> dict:
    """Make the default Rclone SSH key path readable to this service."""
    parameters = config.get("parameters")
    key_file = "/root/.ssh/id_rsa"
    service_key_file = os.getenv("DLM_RCLONE_SSH_KEY_PATH", "/dlm/.ssh/id_rsa")
    if (
        isinstance(parameters, dict)
        and parameters.get("key_file") == key_file
        and os.path.isfile(service_key_file)
    ):
        return {
            **config,
            "parameters": {**parameters, "key_file": service_key_file},
        }
    return config


class Rclone:
    """Invoke Rclone's embedded RPC API through its shared library."""

    def __init__(self, shared_object: str | None = None):
        if shared_object is None:
            shared_object = os.getenv("DLM_RCLONE_LIBRARY_PATH", "/usr/local/lib/librclone.so")
        self._library = CDLL(shared_object)
        self._library.RcloneRPC.restype = _RcloneRPCResult
        self._library.RcloneRPC.argtypes = (c_char_p, c_char_p)
        self._library.RcloneFreeString.restype = None
        self._library.RcloneFreeString.argtypes = (c_char_p,)
        self._library.RcloneInitialize.restype = None
        self._library.RcloneInitialize.argtypes = ()
        self._library.RcloneFinalize.restype = None
        self._library.RcloneFinalize.argtypes = ()
        self._library.RcloneInitialize()

    def rpc(self, method: str, **parameters: Any) -> dict[str, Any]:
        """Call an Rclone RC method and return its JSON object response."""
        library = self._library
        if library is None:
            raise RuntimeError("librclone has already been finalized")
        response = library.RcloneRPC(
            method.encode("utf-8"), json.dumps(parameters).encode("utf-8")
        )
        try:
            output = json.loads(response.Output.value.decode("utf-8"))
        finally:
            library.RcloneFreeString(response.Output)
        if not isinstance(output, dict):
            raise TypeError(f"Rclone RPC {method!r} returned a non-object response")
        if response.Status != 200:
            raise RcloneException(output, response.Status)
        return output

    def close(self) -> None:
        """Finalize librclone once."""
        if self._library is not None:
            self._library.RcloneFinalize()
            self._library = None
