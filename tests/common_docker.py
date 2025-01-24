"""Common utilities for interacting with native system"""


import logging
import os
from pathlib import Path

from overrides import override

import tests.integration.client.dlm_ingest_client as dlm_ingest_requests
import tests.integration.client.dlm_migration_client as dlm_migration_requests
import tests.integration.client.dlm_request_client as dlm_request_requests
import tests.integration.client.dlm_storage_client as dlm_storage_requests
from tests.test_env import DlmTestClient

logger = logging.getLogger(__name__)


class DlmTestClientDocker(DlmTestClient):
    """Docker test environment utilities.

    Test client for a deployment where all services and tests run from
    inside docker.

    This requires the rclone path is hosted on shared filesystem
    mount with the test runtime."""

    def __init__(self):
        dlm_storage_requests.STORAGE_URL = "http://dlm_gateway:8000"
        dlm_ingest_requests.INGEST_URL = "http://dlm_gateway:8000"
        dlm_request_requests.REQUEST_URL = "http://dlm_gateway:8000"
        dlm_migration_requests.MIGRATION_URL = "http://dlm_gateway:8000"

    @property
    def storage_requests(self):
        return dlm_storage_requests

    @property
    def request_requests(self):
        return dlm_request_requests

    @property
    def ingest_requests(self):
        return dlm_ingest_requests

    @property
    def migration_requests(self):
        return dlm_migration_requests

    @override
    def write_rclone_file_content(self, rclone_path: str, content: str):
        self.create_rclone_directory(os.path.dirname(rclone_path))
        # Assume shared file system or docker shared volume
        with open(rclone_path, "wt", encoding="ascii") as file:
            file.write(content)

    @override
    def get_rclone_local_file_content(self, rclone_path: str) -> str:
        with open(rclone_path, "rt", encoding="ascii") as file:
            return file.read()

    @override
    def clear_rclone_data(self, path: str):
        directory = Path(path)
        for item in directory.iterdir():
            if item.is_dir():
                self.clear_rclone_data(item)
            else:
                item.unlink()

    def create_rclone_directory(self, path: str):
        """Create rclone directory."""
        os.makedirs(path, exist_ok=True)

    @override
    def get_gateway_url(self) -> str:
        """Get the gateway url."""
        return "http://dlm_gateway:8000"
