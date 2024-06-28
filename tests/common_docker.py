"""Common utilities for interacting with native system"""

import glob
import logging
import os

logger = logging.getLogger(__name__)

RCLONE_DEPLOYMENT = "ska-dlm-rclone"
RCLONE_HOME = "/data"


# Assume shared file system or docker shared volume
def write_rclone_file_content(rclone_path: str, content: str):
    """Write the given text to a file local to rclone."""
    with open(f"{RCLONE_HOME}/{rclone_path}", "wt", encoding="ascii") as file:
        file.write(content)


def get_rclone_local_file_content(rclone_path: str):
    """Get the text content of a file local to rclone"""
    with open(f"{RCLONE_HOME}/{rclone_path}", "rt", encoding="ascii") as file:
        return file.read()


def clear_rclone_data():
    """Delete all local rclone data."""
    files = glob.glob(f"{RCLONE_HOME}/*")
    for file in files:
        os.remove(file)
