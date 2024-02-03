"""DLMstorage module for ska-data-lifecycle."""

from .dlm_storage_requests import (
    check_item_on_storage,
    check_storage_access,
    create_storage_config,
    get_storage_config,
    init_location,
    init_storage,
    query_location,
    query_storage,
    rclone_access,
    rclone_config,
)

__all__ = [
    "check_item_on_storage",
    "check_storage_access",
    "create_storage_config",
    "get_storage_config",
    "init_location",
    "init_storage",
    "query_location",
    "query_storage",
    "rclone_access",
    "rclone_config",
]

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"
