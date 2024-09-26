"""DLMmigration module for ska-data-lifecycle."""
from .dlm_migration_requests import copy_data_item, rclone_copy

__all__ = ["copy_data_item", "rclone_copy"]

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.1.0"
