"""Convenience functions wrapping the most important postgREST API calls."""

import json
import logging
from typing import Any, Dict, List

import requests
import ska_sdp_metadata_generator as metagen
from fastapi import FastAPI
from ska_sdp_dataproduct_metadata import MetaData

from ska_dlm.cli_utils import fastapi_auto_annotate
from ska_dlm.dlm_storage.dlm_storage_requests import rclone_access
from ska_dlm.typer_types import JsonObjectOption

from .. import CONFIG
from ..data_item import set_metadata, set_state, set_uri
from ..dlm_db.db_access import DB
from ..dlm_request import query_data_item, query_exists
from ..dlm_storage import check_storage_access, query_storage
from ..exceptions import InvalidQueryParameters, UnmetPreconditionForOperation, ValueAlreadyInDB

JsonType = Dict[str, Any] | List[Any] | str | int | float | bool | None
logger = logging.getLogger(__name__)

app = fastapi_auto_annotate(FastAPI(title="DLM Ingest API"))


@app.post("/ingest/init_data_item")
def init_data_item(item_name: str = "", phase: str = "GAS", json_data: str = "") -> str:
    """Intialize a new data_item by at least specifying an item_name.

    Parameters
    ----------
    item_name : str
        the item_name, can be empty, but then json_data has to be specified.
    phase : str
        the phase this item is set to (usually inherited from the storage)
    json_data : str
        provides the ability to specify all values.

    Returns
    -------
    str

    Raises
    ------
    InvalidQueryParameters
    """
    if item_name:
        post_data = {"item_name": item_name, "item_phase": phase}
    elif json_data:
        post_data = json.loads(json_data)
    else:
        raise InvalidQueryParameters("Either item_name or json_data has to be specified!")
    return DB.insert(CONFIG.DLM.dlm_table, json=post_data)[0]["uid"]


@app.post("/ingest/register_data_item")
def register_data_item(  # noqa: C901 # pylint: disable=too-many-arguments
    item_name: str,
    uri: str = "",
    storage_name: str = "",
    storage_id: str = "",
    metadata: JsonObjectOption = None,
    item_format: str | None = "unknown",
    eb_id: str | None = None,
) -> str:
    """Ingest a data_item (register function is an alias).

    This high level function is a combination of init_data_item, set_uri and set_state(READY).
    It also checks whether a data_item is already registered on the requested storage.

    (1) check whether requested storage is known and accessible\n
    (2) check whether item is accessible/exists on that storage\n
    (3) check whether item is already registered on that storage\n
    (4) initialize the new item with the same OID on the new storage\n
    (5) set state to READY\n
    (6) generate metadata\n
    (7) notify the data dashboard

    Parameters
    ----------
    item_name: str
        could be empty, in which case the first 1000 items are returned
    uri: str
        the access path to the payload.
    storage_name: str
        the name of the configured storage volume (name or ID required)
    storage_id: str, optional
        the ID of the configured storage.
    metadata: dict, optional
        metadata provided by the client
    item_format: str, optional
        format of the data item
    eb_id: str | None, optional
        execution block ID provided by the client

    Returns
    -------
    str
        data_item UID

    Raises
    ------
    UnmetPreconditionForOperation
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
    if not rclone_access(storage_name, uri):  # TODO: don't call into rclone directly
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
        "item_format": item_format,
    }
    uid = init_data_item(json_data=json.dumps(init_item))

    # (4)
    set_uri(uid, uri, storage_id)

    # (5) Set data_item state to READY
    set_state(uid, "READY")

    # (6) Populate the metadata column in the database
    metadata_temp = metadata
    if metadata is None:
        try:
            # TODO(yan-xxx) create another RESTful service associated with a storage type
            # and call into the endpoint
            metadata_object = metagen.generate_metadata_from_generator(uri, eb_id)
            metadata_temp = metadata_object.get_data().to_json()
            metadata_temp = json.loads(metadata_temp)
            logger.info("Metadata extracted successfully.")
        except ValueError as err:
            logger.info("ValueError occurred while attempting to extract metadata: %s", err)

    if metadata_temp is not None:
        # Check that metadata_temp is standard json?
        set_metadata(uid, metadata_temp)
        logger.info("Saved metadata provided by client.")
    else:
        metadata_temp = {}

    metadata_temp["uid"] = uid
    metadata_temp["item_name"] = item_name

    # (7)
    notify_data_dashboard(metadata_temp)

    return uid


def notify_data_dashboard(metadata: dict | MetaData) -> None:
    """HTTP POST MetaData json object to the Data Product Dashboard."""
    headers = {"Content-Type": "application/json"}
    url = CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata"

    if isinstance(metadata, MetaData):
        metadata = metadata.get_data()

    # Validation
    payload = None
    try:
        if not isinstance(metadata, dict) or "execution_block" not in metadata:
            raise TypeError(
                f"metadata must contain an 'execution_block', got {type(metadata)} {metadata}"
            )
        payload = json.dumps(metadata)  # --> python obj to json string
    except (TypeError, ValueError) as err:
        logger.error("Failed to parse metadata: %s. Not notifying dashboard.", err)

    if payload is not None:
        try:
            resp = requests.request("POST", url, headers=headers, data=payload, timeout=2)
            resp.raise_for_status()
            logger.info(
                "POSTed metadata (execution_block: %s) to %s", metadata["execution_block"], url
            )
        except requests.RequestException as err:
            logger.exception("POST error notifying dataproduct dashboard at: %s - %s", url, err)
