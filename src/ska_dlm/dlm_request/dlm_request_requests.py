"""Convenience functions wrapping the most important postgREST API calls."""
import logging
from datetime import datetime, timedelta

import requests

from .. import CONFIG

logger = logging.getLogger(__name__)


def query_data_item(
    item_name: str = "", oid: str = "", uid: str = "", query_string: str = ""
) -> str:
    """
    Query a new data_item by at least specifying an item_name.

    Parameters:
    -----------
    item_name: could be empty, in which case the first 1000 items are returned
    oid:    Return data_items referred to by the OID provided.
    uid:    Return data_item referred to by the UID provided.
    query_string: an aribtrary postgREST query string

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
    dat = now.isoformat()
    if offset and isinstance(offset, timedelta):
        dat = now + offset
    elif offset and not isinstance(offset, timedelta):
        logger.warning("Specified offset invalid type! Should be timedelta.")
        return []
    logger.info("Query for expired data_items older than %s", dat, exc_info=1)
    query_string = f"uid_expiration=lt.{dat}&select=uid,uid_expiration"
    result = query_data_item(query_string=query_string)
    return result if result else []
