"""Global test setup/teardown."""

from abc import abstractmethod
from types import ModuleType


class DlmTestClient:
    """
    Test client helper class for a test environment.

    Exposes clients for DLM services and shared test storage.
    """

    @abstractmethod
    def write_rclone_file_content(self, rclone_path: str, content: str):
        """Write the given text to the shared test storage."""
        raise NotImplementedError

    @abstractmethod
    def get_rclone_local_file_content(self, rclone_path: str) -> str:
        """Get the text content of a file in the shared test storage."""
        raise NotImplementedError

    @abstractmethod
    def clear_rclone_data(self, path: str):
        """Delete data in the shared test storage."""
        raise NotImplementedError

    @abstractmethod
    def create_rclone_directory(self, path: str):
        """Create rclone directory."""
        raise NotImplementedError

    @abstractmethod
    def get_gateway_url(self) -> str:
        """Get the gateway url."""
        raise NotImplementedError

    @property
    @abstractmethod
    def storage_requests(self) -> ModuleType:
        """Get storage requests module."""
        raise NotImplementedError

    @property
    @abstractmethod
    def request_requests(self) -> ModuleType:
        """Get request requests module."""
        raise NotImplementedError

    @property
    @abstractmethod
    def data_item_requests(self) -> ModuleType:
        """Get data_item requests module."""
        raise NotImplementedError

    @property
    @abstractmethod
    def ingest_requests(self) -> ModuleType:
        """Get ingest requests module."""
        raise NotImplementedError

    @property
    @abstractmethod
    def migration_requests(self) -> ModuleType:
        """Get migration requests module."""
        raise NotImplementedError
