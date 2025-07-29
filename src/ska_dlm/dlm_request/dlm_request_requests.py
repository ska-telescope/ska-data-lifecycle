"""DLM Request API module."""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum

import ska_ser_logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import ska_dlm
from ska_dlm.data_item.data_item_requests import query_data_item
from ska_dlm.data_item.data_item_requests import rest as data_item_requests
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.fastapi_utils import fastapi_auto_annotate

from ..exceptions import InvalidQueryParameters

logger = logging.getLogger(__name__)
ska_ser_logging.configure_logging(level=logging.INFO)


cli = ExceptionHandlingTyper()
rest = fastapi_auto_annotate(
    FastAPI(
        title="SKA-DLM: Request Manager REST API",
        description="REST interface of the SKA-DLM Request Manager",
        version=ska_dlm.__version__,
        license_info={"name": "BSD-3-Clause", "identifier": "BSD-3-Clause"},
    )
)
rest.include_router(data_item_requests)


class ItemState(str, Enum):
    """Item state."""

    INITIALISED = "INITIALISED"
    READY = "READY"
    CORRUPTED = "CORRUPTED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"


class PhaseType(str, Enum):
    """Phase type / resilience level."""

    GAS = "GAS"
    LIQUID = "LIQUID"
    SOLID = "SOLID"
    PLASMA = "PLASMA"


# pylint: disable=unused-argument
@rest.exception_handler(InvalidQueryParameters)
def invalidquery_exception_handler(request: Request, exc: InvalidQueryParameters):
    """Catch InvalidQueryParameters and send a JSONResponse."""
    return JSONResponse(
        status_code=422,
        content={"exec": "InvalidQueryParameters", "message": f"{str(exc)}"},
    )


@rest.get("/request/query_expired", response_model=list[dict])
def query_expired(offset: timedelta | None = None) -> list[dict]:
    """Query for all expired data_items using the uid_expiration timestamp.

    Parameters
    ----------
    offset
        optional offset for the query

    Returns
    -------
    list[dict]
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
        "item_state": f"eq.{ItemState.READY.value}",
    }
    return query_data_item(params=params)


@cli.command()
@rest.get("/request/query_deleted", response_model=list[dict])
def query_deleted(uid: str = "") -> list[dict]:
    """Query for all deleted data_items using the deleted state.

    Parameters
    ----------
    uid
        The UID to be checked, optional.

    Returns
    -------
    list[dict]
        list of dictionaries with UIDs of deleted items.
    """
    params = {
        "item_state": f"eq.{ItemState.DELETED.value}",
        "select": "uid",
    }
    if uid:
        params["uid"] = f"eq.{uid}"
    return query_data_item(params=params)


@cli.command()
@rest.get("/request/query_new", response_model=list[dict])
def query_new(check_date: str, uid: str = "") -> list[dict]:
    """Query for all data_items newer than the date provided.

    Parameters
    ----------
    check_date
        the UTC starting date (exclusive)
    uid
        The UID to be checked, optional.

    Returns
    -------
    list[dict]
        list of dictionaries with UID, UID_creation and storage_id of new items.
    """
    params = {
        "uid_creation": f"gt.{check_date}",
        "uid_phase": f"eq.{PhaseType.GAS.value}",
        "item_state": f"eq.{ItemState.READY.value}",
        "select": "uid,item_name,uid_creation,storage_id",
    }
    if uid:
        params["uid"] = f"eq.{uid}"
    return query_data_item(params=params)


@cli.command()
@rest.get("/request/query_exists", response_model=bool)
def query_exists(item_name: str = "", oid: str = "", uid: str = "", ready: bool = False) -> bool:
    """Query to check for existence of a data_item.

    Parameters
    ----------
    item_name
        optional item_name
    oid
        the oid to be searched for
    uid
        this returns only one storage_id
    ready
        whether the item must be in READY state.

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
        params["item_state"] = f"eq.{ItemState.READY.value}"
    # TODO: select COUNT(*) only instead of all data columns
    return bool(query_data_item(params=params))


@cli.command()
@rest.get("/request/query_exist_and_ready", response_model=bool)
def query_exists_and_ready(item_name: str = "", oid: str = "", uid: str = "") -> bool:
    """Check whether a data_item exists and is in READY state.

    Parameters
    ----------
    item_name
        optional item_name
    oid
        the oid to be searched for
    uid
        this returns only one storage_id

    Returns
    -------
    bool
        True if the item exists and is in READY state
    """
    return query_exists(item_name, oid, uid, ready=True)


@cli.command()
@rest.get("/request/query_item_storage", response_model=list[dict])
def query_item_storage(item_name: str = "", oid: str = "", uid: str = "") -> list[dict]:
    """
    Query for the storage_ids of all backends holding a copy of a data_item.

    Either an item_name or a OID have to be provided.

    Parameters
    ----------
    item_name
        optional item_name
    oid
        the oid to be searched for
    uid
        this returns only one storage_id

    Returns
    -------
    list[dict]
        list of storage_ids
    """
    if not query_exists_and_ready(item_name, oid, uid):
        logger.warning("data_item does not exists or is not READY.")
        return []
    params = {
        "select": "oid,uid,item_name,storage_id,uri",
        "item_state": f"eq.{ItemState.READY.value}",
    }
    if not item_name and not oid and not uid:
        raise InvalidQueryParameters("Either an item_name or an OID or an UID have to be provided")
    if item_name:
        params["item_name"] = f"eq.{item_name}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif uid:
        params["uid"] = f"eq.{uid}"
    return query_data_item(params=params)
