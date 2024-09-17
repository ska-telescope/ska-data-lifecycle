"""Convenience functions wrapping the most important postgREST API calls."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

from ska_dlm.dlm_db.db_access import DB

from .. import CONFIG
from ..exceptions import InvalidQueryParameters

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SKA-DLM: Request Manager REST I/F",
    description="The REST calls accepted by the SKA-DLM Request Manager"
)


@app.get("/request/query_data_item")
def query_data_item(
    item_name: str = "", oid: str = "", uid: str = "", params: str | None = None
) -> list:
    """
    Query a new data_item by at least specifying an item_name.

    Parameters
    ----------
    item_name: str
        could be empty, in which case the first 1000 items are returned
    oid : str
        Return data_items referred to by the OID provided.
    uid : str
        Return data_item referred to by the UID provided.
    params: str | None
        specify the query parameters

    Returns
    -------
    list
    """
    if bool(params) == (item_name or oid or uid):
        raise InvalidQueryParameters("give either params or item_name/oid/uid")
    params = dict(params) if params else {}
    params["limit"] = 1000
    if item_name:
        params["item_name"] = f"eq.{item_name}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif uid:
        params["uid"] = f"eq.{uid}"
    return DB.select(CONFIG.DLM.dlm_table, params=params)


@app.get("/request/query_expired")
def query_expired(offset: timedelta | None = None):
    """Query for all expired data_items using the uid_expiration timestamp.

    Parameters
    ----------
    offset : timedelta | None, optional
        optional offset for the query
    """
    now = datetime.now(timezone.utc)
    if offset:
        if not isinstance(offset, timedelta):
            raise InvalidQueryParameters("Specified offset invalid type! Should be timedelta.")
        now += offset
    iso_now = now.replace(tzinfo=None).isoformat()
    params = {
        "select": "uid,uid_expiration",
        "uid_expiration": f"lt.{iso_now}",
        "item_state": "eq.READY",
    }
    return query_data_item(params=params)


@app.get("/request/query_deleted")
def query_deleted(uid: str = "") -> list:
    """Query for all deleted data_items using the deleted state.

    Parameters
    ----------
    uid: str
        The UID to be checked, optional.

    Returns
    -------
    list
        list of dictionaries with UIDs of deleted items.
    """
    params = {"item_state": "eq.DELETED", "select": "uid"}
    if uid:
        params["uid"] = f"eq.{uid}"
    return query_data_item(params=params)


@app.get("/request/query_new")
def query_new(check_date: str, uid: str = "") -> list:
    """Query for all data_items newer than the date provided.

    Parameters
    ----------
    check_date: str
        the UTC starting date (exclusive)
    uid: str
        The UID to be checked, optional.

    Returns
    -------
    list
        list of dictionaries with UID, UID_creation and storage_id of new items.
    """
    params = {
        "uid_creation": f"gt.{check_date}",
        "item_phase": "eq.GAS",
        "item_state": "eq.READY",
        "select": "uid,item_name,uid_creation,storage_id",
    }
    if uid:
        params["uid"] = f"eq.{uid}"
    return query_data_item(params=params)


@app.get("/request/query_exists")
def query_exists(item_name: str = "", oid: str = "", uid: str = "", ready: bool = False) -> bool:
    """Query to check for existence of a data_item.

    Parameters
    ----------
    item_name: str, optional
        optional item_name
    oid: str, optional
        the oid to be searched for
    uid: str, optional
        this returns only one storage_id
    ready: bool, optional
        _description_

    Returns
    -------
    bool
        True if the data_item exists
    """
    if not item_name and not oid and not uid:
        raise InvalidQueryParameters("Either an item_name or an OID or an UID have to be provided")
    params = {}
    if item_name:
        params["item_name"] = f"eq.{item_name}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif uid:
        params["uid"] = f"eq.{uid}"
    if ready:
        params["item_state"] = "eq.READY"
    # TODO: select COUNT(*) only instead of all data columns
    return bool(query_data_item(params=params))


@app.get("/request/query_exist_and_ready")
def query_exists_and_ready(item_name: str = "", oid: str = "", uid: str = "") -> bool:
    """Check whether a data_item exists and is in ready state.

    Parameters
    ----------
    item_name: str, optional
        optional item_name
    oid: str, optional
        the oid to be searched for
    uid: str, optional
        this returns only one storage_id

    Returns
    -------
    bool
        True if the item exists and is in ready state
    """
    return query_exists(item_name, oid, uid, ready=True)


@app.get("/request/query_item_storage")
def query_item_storage(item_name: str = "", oid: str = "", uid: str = "") -> list:
    """
    Query for the storage_ids of all backends holding a copy of a data_item.

    Either an item_name or a OID have to be provided.

    Parameters
    ----------
    item_name: str, optional
        optional item_name
    oid: str, optional
        the oid to be searched for
    uid: str, optional
        this returns only one storage_id

    Returns
    -------
    list
        list of storage_ids
    """
    if not query_exists_and_ready(item_name, oid, uid):
        logger.warning("data_item does not exists or is not READY!")
        return []
    params = {"select": "oid,uid,item_name,storage_id,uri", "item_state": "eq.READY"}
    if not item_name and not oid and not uid:
        raise InvalidQueryParameters("Either an item_name or an OID or an UID have to be provided")
    if item_name:
        params["item_name"] = f"eq.{item_name}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif uid:
        params["uid"] = f"eq.{uid}"
    return query_data_item(params=params)
