"""DLMstorage module for ska-data-lifecycle."""

from .dlm_storage_requests import init_location, init_storage, query_location

__all__ = ["query_location", "init_storage", "init_location"]

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"
