"""DLMstorage module for ska-data-lifecycle."""

from .dlm_storage_requests import (
    create_storage_config,
    init_location,
    init_storage,
    query_location,
    query_storage,
)

__all__ = [
    "create_storage_config",
    "init_location",
    "init_storage",
    "query_location",
    "query_storage",
]

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"
