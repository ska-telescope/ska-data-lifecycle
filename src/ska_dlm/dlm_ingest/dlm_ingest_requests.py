"""Convenience functions wrapping the most important postgREST API calls."""

import functools
import json
import logging

import requests
import ska_sdp_metadata_generator.ska_sdp_metadata_generator as metagen
from ska_sdp_dataproduct_metadata import MetaData

from ska_dlm.dlm_storage.dlm_storage_requests import rclone_access

from .. import CONFIG
from ..data_item import set_metadata, set_state, set_uri
from ..dlm_db.db_access import DB
from ..dlm_request import query_data_item, query_exists
from ..dlm_storage import check_storage_access, query_storage
from ..exceptions import InvalidQueryParameters, UnmetPreconditionForOperation, ValueAlreadyInDB

logger = logging.getLogger(__name__)


def init_data_item(item_name: str = "", phase: str = "GAS", json_data: str = "") -> str:
    """
    Intialize a new data_item by at least specifying an item_name.

    Parameters:
    -----------
    item_name, the item_name, can be empty, but then json_data has to be specified.
    phase, the phase this item is set to (usually inherited from the storage)
    json_data, provides the ability to specify all values.

    Returns:
    --------
    uid,
    """
    if item_name:
        post_data = {"item_name": item_name, "item_phase": phase}
    elif json_data:
        post_data = json.loads(json_data)
    else:
        raise InvalidQueryParameters("Either item_name or json_data has to be specified!")
    return DB.insert(CONFIG.DLM.dlm_table, json=post_data)[0]["uid"]


def ingest_data_item(
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
) -> str:
    """
    Ingest a data_item (register function is an alias).

    This high level function is a combination of init_data_item, set_uri and set_state(READY).
    It also checks whether a data_item is already registered on the requested storage.

    (1) check whether requested storage is known and accessible
    (2) check whether item is accessible/exists on that storage
    (3) check whether item is already registered on that storage
    (4) initialize the new item with the same OID on the new storage
    (5) set state to READY
    (6) generate metadata
    (7) notify the data dashboard

    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    uri: the access path to the payload.
    storage_name: the name of the configured storage volume (name or ID required)
    storage_id: optional, the ID of the configured storage.

    Returns:
    --------
    str, data_item UID
    """
    # (1)
    storages = query_storage(storage_name=storage_name, storage_id=storage_id)
    if not storages:
        raise UnmetPreconditionForOperation(
            f"No storages found for {storage_name=}, {storage_id=}"
        )
    storage_id = storages[0]["storage_id"]
    if not check_storage_access(storage_name=storage_name, storage_id=storage_id):
        raise UnmetPreconditionForOperation(
            f"Requested storage volume is not accessible by DLM! {storage_name}"
        )
    # (2)
    if not rclone_access(storage_name, uri):
        raise UnmetPreconditionForOperation(f"File {uri} does not exist on {storage_name}")
    if query_exists(item_name):
        ex_storage_id = query_data_item(item_name)[0]["storage_id"]
        if storage_id == ex_storage_id:
            raise ValueAlreadyInDB(f"Item is already registered on storage! {item_name=}")
    # (3)
    init_item = {
        "item_name": item_name,
        "storage_id": storage_id,
        "item_phase": storages[0]["storage_phase_level"],
    }
    uid = init_data_item(json_data=json.dumps(init_item))

    # (4)
    set_uri(uid, uri, storage_id)

    # (5) Set data_item state to READY
    set_state(uid, "READY")

    # (6) Generate metadata
    # TODO YAN-1746: The following relies on the uri being a local file,
    # rather than being a remote file accessible on rclone.
    metadata_object = metagen.generate_metadata_from_generator(uri)
    set_metadata(uid, metadata_object)  # populate the metadata column in the database

    # (7)
    notify_data_dashboard(metadata_object)

    return uid


def notify_data_dashboard(metadata: MetaData) -> None:
    """HTTP POST a MetaData object to the Data Product Dashboard"""
    headers = {"Content-Type": "application/json"}
    payload = metadata.get_data().to_json()
    url = CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata"

    try:
        requests.request("POST", url, headers=headers, data=payload, timeout=2)
        logger.info("POSTed metadata (%s) to %s", metadata.get_data().execution_block, url)
    except requests.RequestException:
        logger.exception("POST error notifying data dashboard at: %s", url)


# just for convenience we also define the ingest function as register_data_item.
@functools.wraps(ingest_data_item, assigned=set(functools.WRAPPER_ASSIGNMENTS) - {"__name__"})
# pylint: disable-next=missing-function-docstring
def register_data_item(*args, **kwargs) -> str:  # noqa: D103
    return ingest_data_item(*args, **kwargs)
