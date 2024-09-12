"""Global test setup/teardown."""

from abc import abstractmethod
from types import ModuleType


class DlmTestClient:
    """
    Test client helper class for a test environment.

    Exposes a client DLM services and rclone.
    """

    @abstractmethod
    def write_rclone_file_content(self, rclone_path: str, content: str):
        """Write the given text to a file local to rclone."""

    @abstractmethod
    def get_rclone_local_file_content(self, rclone_path: str) -> str:
        """Get the text content of a file local to rclone."""

    @abstractmethod
    def clear_rclone_data(self, path: str):
        """Delete all rclone local data."""

    @abstractmethod
    def get_gateway_url(self) -> str:
        """Get the gateway url."""

    @property
    @abstractmethod
    def storage_requests(self) -> ModuleType:
        """Get storage requests module."""

    @property
    @abstractmethod
    def request_requests(self) -> ModuleType:
        """Get request requests module."""

    @property
    @abstractmethod
    def ingest_requests(self) -> ModuleType:
        """Get ingest requests module."""

    @property
    @abstractmethod
    def migration_requests(self) -> ModuleType:
        """Get migration requests module."""
