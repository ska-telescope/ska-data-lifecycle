"""Convenience functions wrapping the most important postgREST API calls."""
import logging

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
    query_string, an aribtrary postgREST query string

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
    r = requests.get(request_url, timeout=10)
    if r.status_code == 200:
        return r.json()
    logger.info(f"Response status code: {r.status_code}")
    return None
