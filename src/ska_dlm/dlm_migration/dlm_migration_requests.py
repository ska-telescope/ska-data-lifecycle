"""Convenience functions wrapping the most important postgREST API calls."""

import json
import logging

import requests

from ska_dlm.exceptions import InvalidQueryParameters

from .. import CONFIG
from ..data_item import set_state, set_uri
from ..dlm_ingest import init_data_item
from ..dlm_request import query_data_item
from ..dlm_storage import check_item_on_storage, get_storage_config, query_storage
from ..exceptions import UnmetPreconditionForOperation

logger = logging.getLogger(__name__)


def rclone_copy(src_fs: str, src_remote: str, dst_fs: str, dst_remote: str):
    """Copy a file from one place to another."""
    request_url = f"{CONFIG.RCLONE.url}/operations/copyfile"
    post_data = {
        "srcFs": src_fs,
        "srcRemote": src_remote,
        "dstFs": dst_fs,
        "dstRemote": dst_remote,
    }
    logger.info("rclone copy request: %s, %s", request_url, post_data)
    request = requests.post(request_url, post_data, timeout=1800)
    logger.info("Response status code: %s", request.status_code)
    return True


def copy_data_item(  # pylint: disable=too-many-arguments
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    destination_name: str = "",
    destination_id: str = "",
    path: str = "",
) -> str:
    """Copy a data_item from source to destination.

    Steps
    (1) get the current storage_id(s) of the item
    (2) convert one(first) storage_id to a configured rclone backend
    (3) check whether item already exists on destination
    (4) initialize the new item with the same OID on the new storage
    (5) use the rclone copy command to copy it to the new location
    (6) make sure the copy was successful

    Parameters
    ----------
    item_name : str
        data item name, when empty the first 1000 items are returned, by default ""
    oid : str
        object id, Return data_items referred to by the OID provided, by default ""
    uid : str
        Return data_item referred to by the UID provided, by default ""
    destination_name : str
        the name of the destination storage volume, by default ""
    destination_id : str
        the destination storage, by default ""
    path : str
        the destination path, by default ""

    Returns
    -------
    str
        The uid of the new item copy.

    Raises
    ------
    InvalidQueryParameters
        Neither an item_name, OID nor UID parameter provided.
    UnmetPreconditionForOperation
        No data item found for copying.
    """
    if not item_name and not oid and not uid:
        raise InvalidQueryParameters("Either an item_name or an OID or an UID has to be provided!")
    orig_item = query_data_item(item_name, oid, uid)
    if orig_item:
        orig_item = orig_item[0]
    else:
        raise UnmetPreconditionForOperation("No data item found for copying")
    # (1)
    item_name = orig_item["item_name"]
    storages = check_item_on_storage(item_name)
    # we pick the first data_item returned record for now
    if storages:
        storage = storages[0]
    else:
        raise UnmetPreconditionForOperation("Data item not in specified storage")
    # (2)
    s_config = get_storage_config(storage_id=storage["storage_id"])
    if not s_config:
        raise UnmetPreconditionForOperation("No configuration for source storage found!")

    s_config = s_config[0]
    source = {"backend": f"{s_config['name']}:", "path": storage["uri"]}
    if not path:
        path = storage["uri"]
    if destination_name:
        destination = query_storage(storage_name=destination_name)
        if not destination:
            raise UnmetPreconditionForOperation(
                f"Unable to get ID of destination storage: {destination_name}."
            )
        destination_id = destination[0]["storage_id"]
    d_config = get_storage_config(storage_id=destination_id)
    if not d_config:
        raise UnmetPreconditionForOperation("Unable to get configuration for destination storage!")
    d_config = d_config[0]
    dest = {"backend": f"{d_config['name']}:", "path": path}
    # (3)
    init_item = {
        "item_name": item_name,
        "oid": orig_item["oid"],
        "storage_id": destination_id,
    }
    uid = init_data_item(json_data=json.dumps(init_item))
    # (5)
    # TODO(yan-xxx) abstract the actual function called away to allow for different
    # mechanisms to perform the copy. Also needs to be a non-blocking call
    # scheduling a job for dlm_migration service.
    logger.info("source: %s", source)
    rclone_copy(
        source["backend"],
        source["path"],
        dest["backend"],
        dest["path"],
    )
    # (6)
    set_uri(uid, dest["path"], destination_id)
    # all done! Set data_item state to READY
    set_state(uid, "READY")
    return uid
