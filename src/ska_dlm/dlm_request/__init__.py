"""DLMrequest module for ska-data-lifecycle."""
from .dlm_request_requests import query_data_item, query_expired

__all__ = ["query_data_item", "query_expired"]

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"