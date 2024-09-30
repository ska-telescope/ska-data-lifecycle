"""dlm_gateway_client REST client"""

import requests
from requests import Session


def start_session(auth: str, gateway_url: str):
    """Get OAUTH token based on username and password"""
    session = Session()
    bearer = {"Authorization": f"Bearer {auth}"}
    response = session.post(f"{gateway_url}/start_session", headers=bearer, timeout=60)
    response.raise_for_status()
    return session


def has_scope(token: str, permission: str, gateway_url: str):
    """Get UMA"""
    params = {"token": token, "permission": permission}
    response = requests.get(f"{gateway_url}/scope", params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def get_token(username: str, password: str, gateway_url: str):
    """Get OAUTH token based on username and password"""
    params = {"username": username, "password": password}
    response = requests.get(f"{gateway_url}/token_by_username_password", params=params, timeout=60)
    response.raise_for_status()
    return response.json()
