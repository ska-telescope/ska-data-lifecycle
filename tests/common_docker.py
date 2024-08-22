"""Common utilities for interacting with native system"""

import glob
import logging
import os

from overrides import override

import tests.integration.client.dlm_ingest_client as dlm_ingest_requests
import tests.integration.client.dlm_migration_client as dlm_migration_requests
import tests.integration.client.dlm_request_client as dlm_request_requests
import tests.integration.client.dlm_storage_client as dlm_storage_requests
from tests.test_env import DlmTestClient

logger = logging.getLogger(__name__)


class DlmTestClientDocker(DlmTestClient):
    """docker-compose test environment utilities.

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
        # Assume shared file system or docker shared volume
        with open(rclone_path, "wt", encoding="ascii") as file:
            file.write(content)

    @override
    def get_rclone_local_file_content(self, rclone_path: str) -> str:
        with open(rclone_path, "rt", encoding="ascii") as file:
            return file.read()

    @override
    def clear_rclone_data(self, path: str):
        files = glob.glob(f"{path}/*")
        for file in files:
            os.remove(file)

    @override
    def get_service_urls(self) -> dict:
        """Returns named map of the client URLs for each of the DLM services"""
        urls = {
            "dlm_gateway": "http://dlm_gateway:8000",
            "dlm_ingest": "http://dlm_gateway:8000",
            "dlm_request": "http://dlm_gateway:8000",
            "dlm_storage": "http://dlm_gateway:8000",
        }
        return urls
