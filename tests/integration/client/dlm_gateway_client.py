"""dlm_gateway_client REST client"""

import requests

from tests.integration.client.exception_handler import dlm_raise_for_status


def has_scope(token: str, permission: str, gateway_url: str):
    """Get UMA"""
    params = {"token": token, "permission": permission}
    response = requests.get(f"{gateway_url}/scope", params=params, timeout=60)
    dlm_raise_for_status(response)
    return response.json()


def get_token(username: str, password: str, gateway_url: str):
    """Get OAUTH token based on username and password"""
    params = {"username": username, "password": password}
    response = requests.get(f"{gateway_url}/token_by_username_password", params=params, timeout=60)
    dlm_raise_for_status(response)
    return response.json()
