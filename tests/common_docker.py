"""Common utilities for interacting with native system"""

import glob
import logging
import os

logger = logging.getLogger(__name__)

RCLONE_DEPLOYMENT = "ska-dlm-rclone"


# Assume shared file system or docker shared volume
def write_rclone_file_content(rclone_path: str, content: str):
    """Write the given text to a file local to rclone."""
    with open(f"{rclone_path}", "wt", encoding="ascii") as file:
        file.write(content)


def get_rclone_local_file_content(rclone_path: str):
    """Get the text content of a file local to rclone"""
    with open(f"{rclone_path}", "rt", encoding="ascii") as file:
        return file.read()


def clear_rclone_data(path: str):
    """Delete all local rclone data."""
    files = glob.glob(f"{path}/*")
    for file in files:
        os.remove(file)


def get_service_urls():
    """Returns named map of the client URLs for each of the DLM services"""
    urls = {
        "dlm_gateway": "http://dlm_gateway:8000",
        "dlm_ingest": "http://dlm_gateway:8000",
        "dlm_request": "http://dlm_gateway:8000",
        "dlm_storage": "http://dlm_gateway:8000",
    }
    return urls
