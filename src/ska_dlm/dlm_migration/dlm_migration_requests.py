"""Convenience functions wrapping the most important postgREST API calls."""
import json
import logging

import requests

from .. import CONFIG
from ..dlm_ingest import init_data_item, set_state, set_uri
from ..dlm_request import query_data_item
from ..dlm_storage import check_item_on_storage, get_storage_config

logger = logging.getLogger(__name__)


def rclone_copy(src_fs: str, src_remote: str, dst_fs: str, dst_remote: str):
    """
    Copy a file from one place to another.

    NOTE: This assumes a rclone server is running.
    """
    request_url = f"{CONFIG.RCLONE.url}/operations/copyfile"
    post_data = {
        "srcFs": src_fs,
        "srcRemote": src_remote,
        "dstFs": dst_fs,
        "dstRemote": dst_remote,
    }
    logger.info("rclone copy request: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=10)
    logger.info("Response status code: %s", request.status_code)
    return True


def copy_data_item(
    item_name: str = "", oid: str = "", uid: str = "", destination_id: str = "", path: str = ""
) -> bool:
    """
    Copy a data_item from source to destination.

    Steps:
    (1) get the current storage_id(s) of the item
    (2) convert one(first) storage_id to a configured rclone backend
    (3) check whether item already exists on destination
    (4) initialize the new item with the same OID on the new storage
    (5) use the rclone copy command to copy it to the new location
    (6) make sure the copy was successful

    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    oid:    Return data_items referred to by the OID provided.
    uid:    Return data_item referred to by the UID provided.
    destination: the destination storage
    path: the destination path

    Returns:
    --------
    boolean, True if successful
    """
    if not item_name and not oid and not uid:
        logger.error("Either an item_name or an OID or an UID has to be provided!")
        return False
    stat = True
    orig_item = query_data_item(item_name, oid, uid)[0]
    # (1)
    item_name = orig_item["item_name"]
    storages = check_item_on_storage(item_name, storage_id=destination_id)
    # we pick the first data_item returned record for now
    if storages:
        storage = storages[0]
    else:
        return False
    # (2)
    s_config = get_storage_config(storage["storage_id"])
    if not s_config:
        logger.error("No configuration for destination storage found!")
        return False
    source = {"backend": f"{s_config['name']}:", "path": storage["uri"]}
    d_config = get_storage_config(destination_id)
    if not d_config:
        logger.error("No configuration for destination storage found!")
        return False
    dest = {"backend": f"{d_config['name']}:", "path": path}
    # (3)
    init_item = {
        "item_name": item_name,
        "oid": orig_item["oid"],
        "storage_id": destination_id,
    }
    uid = init_data_item(json_data=init_item)
    # (5)
    # TODO: abstract the actual function called away to allow for different
    # mechansims to perform the copy
    logger.info("source: %s", source)
    stat = rclone_copy(
        source["backend"],
        source["path"],
        dest["backend"],
        dest["path"],
    )
    # (6)
    stat = set_uri(uid, dest["path"], destination_id)
    # all done! Set data_item state to READY
    stat = set_state(uid, "READY")
    return stat
