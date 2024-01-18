"""
Convenience functions wrapping the most important postgREST API calls. 
"""

import requests
from .. import CONFIG


def query_data_item(item_name: str = "", query_string: str = "") -> str:
    """
    Query a new data_item by at least specifying an item_name.

    Parameters:
    item_name, could be empty, in which case the first 1000 items
               are returned
    query_string, an aribtrary postgREST query string
    """
    api_url = f"{CONFIG.REST.base_url}/{CONFIG.DLM.dlm_table}?limit=1000"
    if item_name:
        request_url = f"{api_url}&item_name=eq.{item_name}"
    elif query_string:
        request_url = f"{api_url}&{query_string}"
    else:
        request_url = f"{api_url}"
    r = requests.get(request_url)
    if r.status_code == 200:
        return r.json()
    else:
        print(f"Response status code: {r.status_code}")
