"""dlm_gateway_client REST client"""

import requests


def get_token(username: str, password: str, gateway_url: str):
    """Get OAUTH token based on username and password"""
    params = {"username": username, "password": password}
    response = requests.get(f"{gateway_url}/token", params=params, timeout=60)
    response.raise_for_status()
    return response.json()
