"""Convenience functions wrapping the most important postgREST API calls."""
import logging
from datetime import datetime, timedelta

import requests

from .. import CONFIG

logger = logging.getLogger(__name__)


def query_data_item(
    item_name: str = "", oid: str = "", uid: str = "", query_string: str = "", report=True
) -> str:
    """
    Query a new data_item by at least specifying an item_name.

    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    oid:    Return data_items referred to by the OID provided.
    uid:    Return data_item referred to by the UID provided.
    query_string: an aribtrary postgREST query string
    report: If False info is not reported

    Returns:
    --------
    str

    Returns:
    --------
    str
    """
    api_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.dlm_table}?limit=1000"
    if item_name or oid or uid:
        if item_name:
            request_url = f"{api_url}&item_name=eq.{item_name}"
        elif oid:
            request_url = f"{api_url}&oid=eq.{oid}"
        elif uid:
            request_url = f"{api_url}&uid=eq.{uid}"
    elif query_string:
        request_url = f"{api_url}&{query_string}"
    else:
        request_url = f"{api_url}"
    request = requests.get(request_url, timeout=10)
    if request.status_code == 200:
        return request.json()
    if report:
        logger.info("Response status code: %s", request.status_code)
    return None


def query_expired(offset: timedelta = None):
    """
    Query for all expired data_items using the uid_expiration timestamp.

    Parameters:
    -----------
    offset: optional offset for the query
    """
    now = datetime.now()
    iso_now = now.isoformat()
    if offset and isinstance(offset, timedelta):
        iso_now = now + offset
    elif offset and not isinstance(offset, timedelta):
        logger.warning("Specified offset invalid type! Should be timedelta.")
        return []
    logger.info("Query for expired data_items older than %s", iso_now, exc_info=1)
    query_string = f"uid_expiration=lt.{iso_now}&select=uid,uid_expiration"
    result = query_data_item(query_string=query_string)
    return result if result else []


def query_exists(
    item_name: str = "", oid: str = "", uid: str = "", ready: bool = False, report=True
) -> bool:
    """
    Query to check for existence of a data_item.

    Parameters:
    -----------
    item_name: optional item_name
    oid: optional, the oid to be searched for
    uid: optional, this returns only one storage_id
    report: If False do not report error
    """
    if item_name:
        query_string = f"item_name=eq.{item_name}"
    elif oid:
        query_string = f"oid=eq.{oid}"
    elif uid:
        query_string = f"uid=eq.{uid}"
    else:
        if report:
            logger.error("Either an item_name or an OID or an UID have to be provided")
        return False
    if ready is True:
        query_string = f"{query_string}&item_state=eq.READY"
    result = query_data_item(query_string=query_string)
    if not result:
        return False
    return True


def query_exists_and_ready(item_name: str = "", oid: str = "", uid: str = "", report=True) -> bool:
    """
    Check whether a data_item exists and is in ready state.

    Parameters:
    -----------
    item_name: optional item_name
    oid: optional, the oid to be searched for
    uid: optional, this returns only one storage_id
    report: If set to false it does not report errors.

    Returns:
    boolean
    """
    return query_exists(item_name, oid, uid, ready=True, report=report)


def query_item_storage(item_name: str = "", oid: str = "", uid: str = "", report=True) -> str:
    """
    Query for the storage_ids of all backends holding a copy of a data_item.

    Either an item_name or a OID have to be provided.

    Parameters:
    -----------
    item_name: optional item_name
    oid: optional, the oid to be searched for
    uid: optional, this returns only one storage_id
    """
    if not query_exists_and_ready(item_name, oid, uid, report=report):
        if report:
            logger.error("data_item does not exists or is not READY!")
        return []
    select = "&select=oid,uid,item_name,storage_id,storage_name,uri"
    if item_name:
        query_string = f"item_name=eq.{item_name}&item_state=eq.READY{select}"
    elif oid:
        query_string = f"oid=eq.{oid}&item_state=eq.READYx{select}"
    elif uid:
        query_string = f"uid=eq.{uid}&item_state=eq.READY{select}"
    else:
        logger.error("Either an item_name or an OID or an UID have to be provided!")
        return []
    result = query_data_item(query_string=query_string, report=report)
    if not result or not [x["storage_id"] for x in result if x["storage_id"]]:
        if report:
            logger.info("Result: %s", result)
            logger.error("This data_item has no valid storage or it is not in READY state!")
        return []
    return result
