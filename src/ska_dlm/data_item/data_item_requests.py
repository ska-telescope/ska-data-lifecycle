"""Convenience functions to update data_item records."""

import logging
from typing import Any, Dict, List, Literal, Union

from ska_dlm.exceptions import InvalidQueryParameters

from .. import CONFIG
from ..dlm_db.db_access import DB
from ..dlm_request import query_data_item

JsonType = Union[Dict[str, Any], List[Any], str, int, float, bool, None]
# pylint: disable=possibly-used-before-assignment

logger = logging.getLogger(__name__)


def update_data_item(
    item_name: str = "",
    oid: str = "",
    uid: str = "",
    post_data: dict | list[dict] = "",
) -> str | Literal[True]:
    """Update fields of an existing data_item.

    This is mostly used by the other convenience functions. In general when specifying
    an OID or an item_name, multiple entries will be updated at the same time.

    Parameters
    ----------
    item_name : str
        the name of the data_items to be updated
    oid : str
        the OID of the data_items to be updated
    uid : str
        the UID of the data_item to be updated
    post_data : dict | list[dict]
        the json formatted update data, compatible with postgREST

    Returns
    -------
    str | Literal[True]

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
    return DB.update(CONFIG.DLM.dlm_table, params=params, json=post_data)[0]["uid"]


def set_uri(uid: str, uri: str, storage_id: str):
    """Set the URI field of the uid data_item.

    Parameters
    ----------
    uid : str
        the uid of the data_item to be updated
    uri : str
        the access URI for the data_item
    storage_id : str
        the storage_id associated with the URI
    """
    update_data_item(uid=uid, post_data={"uri": uri, "storage_id": storage_id})


def set_metadata(uid: str, metadata_post: JsonType):
    """
    Populate the metadata column for a data_item with the metadata.

    Parameters
    ----------
    uid : str
        the UID of the data_item to be updated
    metadata_post : MetaData
        a metadata JSON string
    """
    update_data_item(uid=uid, post_data={"metadata": metadata_post})


def set_state(uid: str, state: str) -> str | Literal[True]:
    """Set the state field of the uid data_item.

    Parameters
    ----------
    uid : str
        the uid of the data_item to be updated
    state : str
        the new state for the data_item

    Returns
    -------
    str | Literal[True]
    """
    return update_data_item(uid=uid, post_data={"item_state": state})


def set_oid_expiration(oid: str, expiration: str) -> str:
    """Set the oid_expiration field of the data_items with the given OID.

    Parameters
    ----------
    oid : str
        the oid of the data_item to be updated
    expiration : str
        the expiration date for the data_item

    Returns
    -------
    str
    """
    return update_data_item(oid=oid, post_data={"oid_expiration": expiration})


def set_uid_expiration(uid: str, expiration: str) -> str | Literal[True]:
    """Set the uid_expiration field of the data_item with the given UID.

    Parameters
    ----------
    uid : str
        the UID of the data_item to be updated
    expiration : str
        the expiration date for the data_item

    Returns
    -------
    str | Literal[True]
    """
    return update_data_item(uid=uid, post_data={"uid_expiration": expiration})


def set_user(oid: str = "", uid: str = "", user: str = "SKA") -> str | Literal[True]:
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters
    ----------
    oid : str
        the OID of the data_item to be updated
    uid : str
        the UID of the data_item to be updated
    user : str
        the user for the data_item

    Returns
    -------
    str | Literal[True]

    Raises
    ------
    InvalidQueryParameters
        When neither oid or uid is given
    """
    if not (uid or oid):
        raise InvalidQueryParameters("Either oid or uid should be specified")
    post_data = {"user": user}
    if uid:
        res = update_data_item(uid=uid, post_data=post_data)
    elif oid:
        res = update_data_item(oid=oid, post_data=post_data)
    return res


def set_group(oid: str = "", uid: str = "", group: str = "SKA") -> str | Literal[True]:
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters
    ----------
    oid : str
        the OID of the data_item to be updated
    uid : str
        the UID of the data_item to be updated
    group : str
        the group for the data_item

    Returns
    -------
    str | Literal[True]

    Raises
    ------
    InvalidQueryParameters
        When neither oid or uid is given
    """
    if not (uid or oid):
        raise InvalidQueryParameters("Either oid or uid should be specified")
    post_data = {"group": group}
    if uid:
        res = update_data_item(uid=uid, post_data=post_data)
    elif oid:
        res = update_data_item(oid=oid, post_data=post_data)
    return res


def set_acl(oid: str = "", uid: str = "", acl: str = "{}") -> str | Literal[True]:
    """
    Set the user field of the data_item(s) with the given OID or UID.

    Parameters
    ----------
    oid : str
        the OID of the data_item to be updated
    uid : str
        the UID of the data_item to be updated
    acl : str
        the acl dict for the data_item

    Returns
    -------
    str | Literal[True]

    Raises
    ------
    InvalidQueryParameters
        When neither oid or uid is given
    """
    if not (uid or oid):
        raise InvalidQueryParameters("Either oid or uid should be specified")
    post_data = {"acl": acl}
    if uid:
        res = update_data_item(uid=uid, post_data=post_data)
    elif oid:
        res = update_data_item(oid=oid, post_data=post_data)
    return res


def set_phase(uid: str, phase: str) -> str | Literal[True]:
    """
    Set the phase field of the data_item(s) with given UID.

    Parameters
    ----------
    uid : str
        the UID of the data_item to be updated
    phase : str
        the phase for the data_item

    Returns
    -------
    str | Literal[True]
    """
    return update_data_item(uid=uid, post_data={"item_phase": phase})


def update_item_tags(item_name: str = "", oid: str = "", item_tags: dict | None = None) -> bool:
    """
    Update/set the item_tags field of a data_item with given item_name/OID.

    This will update all records for a data_item at the same time.
    Updating a single UID does not make sense.

    Parameters
    ----------
    item_name: str
        the name of the data_item
    oid : str
        the OID of the data_item to be updated
    item_tags : dict | None
        dictionary of keyword/value pairs

    Returns
    -------
    bool
    """
    if (not item_name and not oid) or not item_tags:
        logger.error("Either item_name or OID or item_tags are missing")
        return False

    result = query_data_item(item_name, oid)
    if not result:
        return False
    oid, existing_tags = (result[0]["oid"], result[0]["item_tags"])
    tags = {} if not existing_tags else existing_tags
    print(f"Existing tags: {tags}")
    tags.update(item_tags)  # merge existing with new ones
    return bool(update_data_item(oid=oid, post_data={"item_tags": tags}))
