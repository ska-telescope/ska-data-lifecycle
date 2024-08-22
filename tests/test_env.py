"""Global test setup/teardown."""

from abc import abstractmethod
from types import ModuleType


class TestClient:
    """
    Test client helper class for a test environment.

    Exposes a client DLM services and rclone.
    """

    @abstractmethod
    def write_rclone_file_content(self, rclone_path: str, content: str):
        """Write the given text to a file local to rclone."""

    @abstractmethod
    def get_rclone_local_file_content(self, rclone_path: str):
        """Get the text content of a file local to rclone."""

    @abstractmethod
    def clear_rclone_data(self, path: str):
        """Delete all rclone local data."""

    @abstractmethod
    def get_service_urls(self) -> dict:
        """Get the named map of the DLM client URLs reachable from the test suite.

        Returns
        -------
        dict
            named map of services to urls
        """

    @property
    @abstractmethod
    def storage_requests(self) -> ModuleType:
        pass

    @property
    @abstractmethod
    def request_requests(self) -> ModuleType:
        pass

    @property
    @abstractmethod
    def ingest_requests(self) -> ModuleType:
        pass

    @property
    @abstractmethod
    def migration_requests(self) -> ModuleType:
        pass
