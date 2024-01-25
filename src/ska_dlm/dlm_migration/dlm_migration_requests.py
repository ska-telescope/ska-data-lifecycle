"""Convenience functions wrapping the most important postgREST API calls."""
import logging

import requests

from .. import CONFIG
from ..dlm_request import query_item_storage

logger = logging.getLogger(__name__)


def rclone_copy(src_fs: str, src_remote: str, dst_fs: str, dst_remote: str):
    """
    Helper function copying a file from a one place to another.
    NOTE: This assumes a rclone server is running locally
    """
    request_url = "http://localhost:5572/operations/copyfile"
    post_data = {
        "srcFs": src_fs,
        "srcRemote": src_remote,
        "dstFs": dst_fs,
        "dstRemote": dst_remote,
    }
    request = requests.post(request_url, post_data, timeout=10)
    logger.info("Response status code: %s", request.status_code)
    return {}


def copy_data_item(
    item_name: str = "", oid: str = "", uid: str = "", destination: str = ""
) -> str:
    """
    Copy a data_item from source to destination.


    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    oid:    Return data_items referred to by the OID provided.
    uid:    Return data_item referred to by the UID provided.
    destination: the destination storage and path

    Returns:
    --------
    str
    """
    # Steps:
    # 1) get the current storage_id(s) of the item
    # 2) convert one storage_id to a configured rclone backend
    # 3) use the rclone copy command to copy it to the new location
    # 4) make sure the copy was successful
    # 5) register the new item with the same OID and a new UID

    if not item_name and not oid and not uid:
        logger.error("Either an item_name or an OID or an UID have to be provided!")
        return []
    storages = query_item_storage(item_name, oid, uid)
    if not storages:
        logger.error("No storage is keeping this data_item!")
        return []

    rclone_copy(
        storages[0]["backend"], storages[0]["path"], destination["backend"], destination["path"]
    )

    return []
