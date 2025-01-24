"""Common utilities for interacting with native system"""

import logging
import os
import tarfile

import docker
from overrides import override

from ska_dlm import dlm_ingest, dlm_migration, dlm_request, dlm_storage
from tests.test_env import DlmTestClient

logger = logging.getLogger(__name__)

RCLONE_DEPLOYMENT = "dlm_rclone"


class DlmTestClientLocal(DlmTestClient):
    """Local test environment utilities.

    Does not utilize containerised DLM production code.
    """

    @property
    def storage_requests(self):
        return dlm_storage.dlm_storage_requests

    @property
    def request_requests(self):
        return dlm_request.dlm_request_requests

    @property
    def ingest_requests(self):
        return dlm_ingest.dlm_ingest_requests

    @property
    def migration_requests(self):
        return dlm_migration.dlm_migration_requests

    def __init__(self):
        self.client = docker.from_env()

    def _copy_to(self, src: str, dst: str):
        """Copy file to container"""
        name, dst = dst.split(":")
        container = self.client.containers.get(name)
        with tarfile.open(f"{src}.tar", "w") as tar:
            tar.add(src, arcname=os.path.basename(src))

        container.exec_run(f"mkdir -p {os.path.dirname(dst)}")

        with open(f"{src}.tar", "rb") as data:
            container.put_archive(os.path.dirname(dst), data.read())

    def _copy_from(self, src: str, dest: str):
        """Copy file from container"""
        name, src = src.split(":")
        container = self.client.containers.get(name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        with open(dest, "wb") as file:
            bits, _ = container.get_archive(src)
            for chunk in bits:
                file.write(chunk)

    @override
    def write_rclone_file_content(self, rclone_path: str, content: str):
        """Write the given text to a file local to rclone container."""
        os.makedirs(f"/tmp/{os.path.dirname(rclone_path)}", exist_ok=True)
        with open(f"/tmp/{rclone_path}", "wt", encoding="ascii") as file:
            file.write(content)

        self._copy_to(f"/tmp/{rclone_path}", f"{RCLONE_DEPLOYMENT}:{rclone_path}")

    @override
    def get_rclone_local_file_content(self, rclone_path: str) -> str:
        """Get the text content of a file local to rclone container"""
        self._copy_from(f"{RCLONE_DEPLOYMENT}:{rclone_path}", f"/tmp/{rclone_path}.tar")

        with tarfile.open(f"/tmp/{rclone_path}.tar") as file:
            file.extractall("/tmp", filter="data")

        with open(f"/tmp/{os.path.basename(rclone_path)}", "rt", encoding="ascii") as file:
            return file.read()

    @override
    def clear_rclone_data(self, path: str):
        container = self.client.containers.get(RCLONE_DEPLOYMENT)
        container.exec_run(["/bin/sh", "-c", f"rm -rf {path}/*"])

    def create_rclone_directory(self, path: str):
        """Create rclone directory."""
        container = self.client.containers.get(RCLONE_DEPLOYMENT)
        container.exec_run(f"mkdir -p {path}")

    @override
    def get_gateway_url(self) -> str:
        """Get the gateway url."""
        return "http://localhost:8000"
