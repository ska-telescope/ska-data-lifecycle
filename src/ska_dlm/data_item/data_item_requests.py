"""Convenience functions to update data_item records."""

import logging

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.exceptions import InvalidQueryParameters
from ska_dlm.fastapi_utils import fastapi_auto_annotate
from ska_dlm.typer_types import JsonObjectOption
from ska_dlm.dlm_db.dlm_models import DataItem
from ska_dlm.dlm_db.db_direct_access import DB_DIRECT_SESSION, db_direct_engine

logger = logging.getLogger(__name__)

cli = ExceptionHandlingTyper()

rest = fastapi_auto_annotate(APIRouter())

def serialise_data_item(item: DataItem) -> dict:
    """Serialise data item then return as dict."""
    return {
        "uid": str(item.uid),
        "oid": str(item.oid) if item.oid else None,
        "item_name": item.item_name,
        "item_version": item.item_version,
        "item_tags": item.item_tags,
        "storage_id": str(item.storage_id) if item.storage_id else None,
        "uri": item.uri,
        "item_value": item.item_value,
        "item_type": item.item_type,
        "item_format": item.item_format,
        "item_encoding": item.item_encoding,
        "item_mime_type": item.item_mime_type,
        "item_level": item.item_level,
        "uid_phase": item.uid_phase,
        "oid_phase": item.oid_phase,
        "item_state": item.item_state,
        "uid_creation": item.uid_creation.isoformat() if item.uid_creation else None,
        "oid_creation": item.oid_creation.isoformat() if item.oid_creation else None,
        "uid_expiration": item.uid_expiration.isoformat() if item.uid_expiration else None,
        "oid_expiration": item.oid_expiration.isoformat() if item.oid_expiration else None,
        "uid_deletion": item.uid_deletion.isoformat() if item.uid_deletion else None,
        "oid_deletion": item.oid_deletion.isoformat() if item.oid_deletion else None,
        "expired": item.expired,
        "deleted": item.deleted,
        "last_access": item.last_access.isoformat() if item.last_access else None,
        "item_checksum": item.item_checksum,
        "checksum_method": item.checksum_method,
        "last_check": item.last_check.isoformat() if item.last_check else None,
        "item_owner": item.item_owner,
        "item_group": item.item_group,
        "acl": item.acl,
        "activate_method": item.activate_method,
        "item_size": item.item_size,
        "decompressed_size": item.decompressed_size,
        "compression_method": item.compression_method,
        "parents": str(item.parents) if item.parents else None,
        "children": str(item.children) if item.children else None,
        "metadata": item.metadata_,
    }

# Possbile new code for SQLAlchemy
# The generality for params here needs to be removed but this is for initial porting

from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect
from datetime import datetime
from typing import Type, Any
import operator as py_operator

# Mapping PostgREST operators to Python/SQLAlchemy logic
OPERATOR_MAP = {
    'eq': py_operator.eq,
    'neq': py_operator.ne,
    'lt': py_operator.lt,
    'lte': py_operator.le,
    'gt': py_operator.gt,
    'gte': py_operator.ge,
    'like': lambda col, val: col.like(val),
    'ilike': lambda col, val: col.ilike(val),
    'in': lambda col, val: col.in_(val.split(',')),
    'is': lambda col, val: col.is_(None) if val.lower() == 'null' else col == val,
}

def parse_value(value: str) -> Any:
    """Try to parse as datetime, otherwise return string."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return value

def resolve_column(model, field_path: str, query_obj, joins: dict):
    """Resolve dotted field paths (e.g. 'storage.name') and apply joins as needed."""
    parts = field_path.split(".")
    current_model = model
    attr = None

    for i, part in enumerate(parts):
        attr = getattr(current_model, part)
        # Detect if this is a relationship (needs join)
        if hasattr(attr, "property") and hasattr(attr.property, "mapper"):
            rel_model = attr.property.mapper.class_
            join_key = ".".join(parts[:i + 1])
            if join_key not in joins:
                query_obj = query_obj.join(attr)
                joins[join_key] = rel_model
            current_model = rel_model
        else:
            # We've reached a column (not a relationship)
            return attr, query_obj

    return attr, query_obj

def select_from_model(
        session: Session,
        model: Type,
        params: dict
) -> list[dict]:
    params = params.copy()  # Avoid mutating original dict
    joins = {}
    query = session.query()

    # Handle 'select' (optional)
    if 'select' in params:
        select_fields = [field.strip() for field in params.pop('select').split(',')]
    else:
        # Select all columns from base model
        mapper = inspect(model)
        select_fields = [attr.key for attr in mapper.column_attrs]

    # Handle limit (optional)
    limit = int(params.pop('limit', 0))

    # Build query with correct joins and column paths
    columns = []
    for field in select_fields:
        col, query = resolve_column(model, field, query, joins)
        columns.append(col)
    query = query.with_entities(*columns)

    # Apply filters
    for key, expression in params.items():
        if '.' not in expression:
            raise ValueError(f"Invalid filter expression: '{expression}'")
        op_key, value = expression.split('.', 1)

        # Resolve column (with join if needed)
        col, query = resolve_column(model, key, query, joins)

        op_func = OPERATOR_MAP.get(op_key)
        if not op_func:
            raise ValueError(f"Unsupported operator: '{op_key}'")

        query = query.filter(op_func(col, parse_value(value)))

    if limit > 0:
        query = query.limit(limit)

    results = query.all()
    return [dict(zip(select_fields, row)) for row in results]


# End of possbile new code



@cli.command()
@rest.get("/request/query_data_item", response_model=list[dict])
def query_data_item(
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    storage_id: str = "",
    params: str | None = None,  # TODO: meant to be dict | None
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
    if item_name:
        params["item_name"] = f"eq.{item_name}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif uid:
        params["uid"] = f"eq.{uid}"

    if storage_id:
        params["storage_id"] = f"eq.{storage_id}"

    logger.info(f"query_data_item.params: {params}")

    db_select = DB.select(CONFIG.DLM.dlm_table, params=params)
    logger.info(f"query_data_item.db_select: {len(db_select)}")
    if len(db_select) >= 1:
        logger.info(f"query_data_item.db_select: {db_select[0]}")

    #logger.info(f"*****************************************************************************")
    #logger.info(f"db_select: {db_select}")
    #logger.info(f"*****************************************************************************")
    #logger.info(f"")
    #logger.info(f"*****************************************************************************")

    session = sessionmaker(bind=db_direct_engine)()
    logger.info("sessionmaker done")
    results = select_from_model(session=session, model=DataItem, params=params)
    logger.info("results done")
    #stmt = select(DataItem).params(params=params)
    #results = session.execute(stmt).scalars().all()
    list_dict_result = results
    #logger.info(f"select on params data_item_result: {results}")
    #list_dict_result = [serialise_data_item(row) for row in results]
    logger.info(f"select on params data_item_result: {len(list_dict_result)}")
    if len(list_dict_result) >= 1:
        logger.info(f"select on params data_item_result: {list_dict_result[0]}")
    #logger.info(f"*****************************************************************************")

    session.close()
    return list_dict_result

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
    if item_name:
        params["item_name"] = f"eq.{item_name}"
    elif oid:
        params["oid"] = f"eq.{oid}"
    elif uid:
        params["uid"] = f"eq.{uid}"
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
def set_state(uid: str, state: str) -> dict:
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
    return update_data_item(uid=uid, post_data={"item_state": state})


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
