"""Convenience functions to update data_item records."""

import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from ska_dlm import CONFIG
from ska_dlm.common_types import ItemState, ItemType
from ska_dlm.dlm_db import DataItem, DataItemChildren
from ska_dlm.dlm_db.db_access import DB
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.exceptions import InvalidQueryParameters
from ska_dlm.fastapi_utils import fastapi_auto_annotate
from ska_dlm.typer_types import JsonObjectOption

logger = logging.getLogger(__name__)

cli = ExceptionHandlingTyper()

rest = fastapi_auto_annotate(APIRouter())


async def _get_data_item_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped SQLAlchemy session."""
    session_factory = getattr(request.app.state, "async_session_factory", None)
    if session_factory is None:
        logger.error("Request API SQLAlchemy session factory is not initialized")
        raise HTTPException(
            status_code=500,
            detail={
                "exec": "DatabaseUnavailable",
                "message": "SQLAlchemy session factory is not initialized",
            },
        )
    async with session_factory() as session:
        yield session


def _data_item_to_dict(data_item: DataItem) -> dict[str, object]:
    """Convert a data-item ORM object to its database column names and values."""
    return {
        prop.columns[0].name: getattr(data_item, prop.key)
        for prop in inspect(DataItem).mapper.column_attrs
    }


@cli.command()
@rest.get("/request/query_data_item", response_model=list[dict])
def query_data_item(
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    storage_id: str = "",
    params: str | None = None,
) -> list[dict]:
    """Query a data_item.

    params or item_name/oid/uid is required.

    Parameters
    ----------
    item_name
        Could be empty, in which case the first 1000 items are returned
    oid
        Return data_items referred to by the OID provided.
    uid
        Return data_item referred to by the UID provided.
    storage_id
        Return data_item referred to by a given storage_id.
    params
        specify the query parameters

    Returns
    -------
    list[dict]
        data item ids.
    """
    if bool(params) == (item_name or oid or uid):
        raise InvalidQueryParameters("give either params or item_name/oid/uid")
    params = dict(params) if params else {}
    params["limit"] = 1000
    if uid:
        params["uid"] = f"eq.{uid}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif item_name:
        params["item_name"] = f"eq.{item_name}"

    if storage_id:
        params["storage_id"] = f"eq.{storage_id}"

    return DB.select(CONFIG.DLM.dlm_table, params=params)


@rest.get("/request/get_data_item", response_model=dict)
async def get_data_item(
    oid: UUID, session: Annotated[AsyncSession, Depends(_get_data_item_session)]
) -> dict[str, object]:
    """Get the first data item matching an OID, including immediate container children.

    Parameters
    ----------
    oid
        The OID of the data item to retrieve.

    session
        Asynchronous database session for performing the retrieval operation.

    Returns
    -------
    dict
        The matching data item. For containers, children contains immediate child
        data items with only their UID, OID, and item name.

    Raises
    ------
    HTTPException
        If no data item matches the OID or a database operation fails.
    """
    try:
        result = await session.execute(select(DataItem).where(DataItem.OID == oid).limit(1))
        data_item_record = result.scalars().first()
        if data_item_record is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "exec": "DataItemNotFound",
                    "message": f"No data item found for OID {oid}",
                },
            )

        data_item = _data_item_to_dict(data_item_record)
        if data_item_record.item_type == ItemType.CONTAINER.value:
            data_item["children"] = []
            children_query = (
                select(
                    DataItem.UID.label("uid"),
                    DataItem.OID.label("oid"),
                    DataItem.item_name.label("item_name"),
                )
                .join(DataItemChildren, DataItem.UID == DataItemChildren.data_item_uid)
                .where(DataItemChildren.parent_data_item_uid == data_item_record.UID)
            )
            children_result = await session.execute(children_query)
            data_item["children"] = [dict(child) for child in children_result.mappings().all()]

        return data_item
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve data item for OID %s", oid)
        raise HTTPException(
            status_code=500,
            detail={"exec": type(exc).__name__, "message": "Unable to retrieve data item"},
        ) from exc


@cli.command()
@rest.patch("/request/update_data_item", response_model=dict)
def update_data_item(
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    post_data: JsonObjectOption = None,
) -> dict:
    """Update fields of an existing data_item.

    This is mostly used by the other convenience functions. In general when specifying
    an OID or an item_name, multiple entries will be updated at the same time.

    Parameters
    ----------
    item_name
        the name of the data_items to be updated
    oid
        the OID of the data_items to be updated
    uid
        the UID of the data_item to be updated
    post_data
        the json formatted update data, compatible with postgREST

    Returns
    -------
    dict
        the updated data item entry

    Raises
    ------
    InvalidQueryParameters
        When neither item_name, oid or uid is given
    """
    if not (item_name or oid or uid):
        raise InvalidQueryParameters("Either item_name, oid or uid must be given")
    params = {}
    if uid:
        params["uid"] = f"eq.{uid}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif item_name:
        params["item_name"] = f"eq.{item_name}"
    return DB.update(CONFIG.DLM.dlm_table, params=params, json=post_data)[0]


@cli.command()
@rest.patch("/request/set_uri", response_model=dict)
def set_uri(uid: str, uri: str, storage_id: str) -> dict:
    """Set the URI field of the uid data_item.

    Parameters
    ----------
    uid
        the uid of the data_item to be updated
    uri
        the access URI for the data_item
    storage_id
        the storage_id associated with the URI

    Returns
    -------
    dict
        the updated data item entry
    """
    return update_data_item(uid=uid, post_data={"uri": uri, "storage_id": storage_id})


@cli.command()
@rest.patch("/request/set_metadata", response_model=dict)
def set_metadata(uid: str, metadata_post: JsonObjectOption = None) -> dict:
    """
    Populate the metadata column for a data_item with the metadata.

    Parameters
    ----------
    uid
        the UID of the data_item to be updated
    metadata_post
        a metadata JSON string

    Returns
    -------
    dict
    """
    return update_data_item(uid=uid, post_data={"metadata": metadata_post})


@cli.command()
@rest.patch("/request/set_state", response_model=dict)
def set_state(uid: str, state: ItemState) -> dict:
    """Set the state field of the uid data_item.

    Parameters
    ----------
    uid
        the uid of the data_item to be updated
    state
        the new state for the data_item

    Returns
    -------
    dict
        the updated data item entry
    """
    try:
        state = ItemState(state)  # Convert input to a valid enum entry
    except ValueError as exc:
        raise ValueError(
            f"Invalid item state {state}. Must be one of {[e.value for e in ItemState]}"
        ) from exc
    deleted_flag = state == "DELETED"
    return update_data_item(
        uid=uid, post_data={"item_state": state.value, "deleted": deleted_flag}
    )


@cli.command()
@rest.patch("/request/set_oid_expiration", response_model=dict)
def set_oid_expiration(oid: str, expiration: str) -> dict:
    """Set the oid_expiration field of the data_items with the given OID.

    Parameters
    ----------
    oid
        the oid of the data_item to be updated
    expiration
        the expiration date for the data_item

    Returns
    -------
    dict
        the updated data item entry
    """
    return update_data_item(oid=oid, post_data={"oid_expiration": expiration})


@cli.command()
@rest.patch("/request/set_uid_expiration", response_model=dict)
def set_uid_expiration(uid: str, expiration: str) -> dict:
    """Set the uid_expiration field of the data_item with the given UID.

    Parameters
    ----------
    uid
        the UID of the data_item to be updated
    expiration
        the expiration date for the data_item

    Returns
    -------
    dict
        the updated data item entry
    """
    return update_data_item(uid=uid, post_data={"uid_expiration": expiration})


@cli.command()
@rest.patch("/request/set_user", response_model=dict)
def set_user(oid: str = "", uid: str = "", user: str = "SKA") -> dict:
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters
    ----------
    oid
        the OID of the data_item to be updated
    uid
        the UID of the data_item to be updated
    user
        the user for the data_item

    Returns
    -------
    dict
        the updated data item entry

    Raises
    ------
    InvalidQueryParameters
        When neither oid or uid is given
    """
    if not (uid or oid):
        raise InvalidQueryParameters("Either oid or uid should be specified")
    post_data = {"user": user}
    return update_data_item(uid=uid, oid=oid, post_data=post_data)


@cli.command()
@rest.patch("/request/set_group", response_model=dict)
def set_group(oid: str = "", uid: str = "", group: str = "SKA") -> dict:
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters
    ----------
    oid
        the OID of the data_item to be updated
    uid
        the UID of the data_item to be updated
    group
        the group for the data_item

    Returns
    -------
    dict
        the updated data item entry

    Raises
    ------
    InvalidQueryParameters
        When neither oid or uid is given
    """
    if not (uid or oid):
        raise InvalidQueryParameters("Either oid or uid should be specified")
    post_data = {"group": group}
    return update_data_item(uid=uid, oid=oid, post_data=post_data)


@cli.command()
@rest.patch("/request/set_acl", response_model=dict)
def set_acl(oid: str = "", uid: str = "", acl: str = "{}") -> dict:
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters
    ----------
    oid
        the OID of the data_item to be updated
    uid
        the UID of the data_item to be updated
    acl
        the acl dict for the data_item

    Returns
    -------
    dict
        the updated data item entry

    Raises
    ------
    InvalidQueryParameters
        When neither oid or uid is given
    """
    if not (uid or oid):
        raise InvalidQueryParameters("Either oid or uid should be specified")
    post_data = {"acl": acl}
    return update_data_item(uid=uid, oid=oid, post_data=post_data)


@cli.command()
@rest.patch("/request/set_phase", response_model=dict)
def set_phase(uid: str, phase: str) -> dict:
    """
    Set the phase field of the data_item(s) with given UID.

    Parameters
    ----------
    uid
        the UID of the data_item to be updated
    phase
        the phase for the data_item

    Returns
    -------
    dict
        the updated data item entry
    """
    return update_data_item(uid=uid, post_data={"uid_phase": phase})


@cli.command()
@rest.patch("/request/update_item_tags", response_model=dict)
def update_item_tags(
    item_name: str = "", oid: str = "", item_tags: JsonObjectOption = None
) -> dict:
    """
    Update/set the item_tags field of a data_item with given item_name/OID.

    This will update all records for a data_item at the same time.
    Updating a single UID does not make sense.

    Parameters
    ----------
    item_name
        the name of the data_item
    oid
        the OID of the data_item to be updated
    item_tags
        dictionary of keyword/value pairs

    Returns
    -------
    dict
        the updated data item entry
    """
    if (not item_name and not oid) or not item_tags:
        raise InvalidQueryParameters("Either item_name or OID or item_tags are missing")

    result = query_data_item(item_name, oid)
    if not result:
        raise InvalidQueryParameters("item_name or OID not found")

    oid, existing_tags = (result[0]["oid"], result[0]["item_tags"])
    tags = {} if not existing_tags else existing_tags
    logging.info("Updating tags: %s with %s", tags, item_tags)
    tags.update(item_tags)  # merge existing with new ones
    return update_data_item(oid=oid, post_data={"item_tags": tags})


@cli.command()
def delete_data_item_entry(uid: str) -> None:
    """
    Delete data item from the data_item table.

    Parameters
    ----------
    uid
        uid of the data_item
    """
    params = {"uid": f"eq.{uid}"}
    DB.delete(CONFIG.DLM.dlm_table, params=params)
    logger.info("Deleted entry %s from data_item table", uid)
