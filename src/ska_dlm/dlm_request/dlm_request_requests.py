"""
Convenience functions wrapping the most important postgREST API calls. 
"""

import requests


def init_data_item(item_name: str, **kwargs) -> str:
    """
    Intialize a new data_item by at least specifying an item_name.

    Parameters:
    item_name
    """
    pass


def set_uri(uid: str, uri: str):
    """ """
    pass


def set_state(uid: str, state):
    """ """
    pass


def set_oid_expiration(oid: str, expiration: str):
    """ """
    pass


def set_uid_expiration(uid: str, expiration: str):
    """ """
    pass


def set_user(oid: str = "", uid: str = "", user: str = "SKA"):
    """ """
    pass


def set_group(oid: str = "", uid: str = "", group: str = "SKA"):
    """ """
    pass


def set_acl(oid: str = "", uid: str = "", acl: str = "{}") -> uid:
    """ """
    pass
