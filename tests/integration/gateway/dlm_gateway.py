"""API Gateway."""

import asyncio
import json
import logging
import os
import ssl
from abc import abstractmethod
from functools import partial
from typing import Any

import httpx
import jwt
import jwt.algorithms
import msal
import requests
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from keycloak import KeycloakOpenID, KeycloakUMA
from keycloak.exceptions import KeycloakAuthenticationError
from overrides import override
from starlette.background import BackgroundTask
from starlette.middleware.sessions import SessionMiddleware


class Provider:
    """Represents base class for an OIDC Provider."""

    def __init__(self):
        pass

    @abstractmethod
    async def token_by_auth_flow(self, request: Request) -> Response:
        """Initiate Auth flow to obain a token.

        Redirects to IdP for Authentication/Authorization.

        Parameters
        ----------
        request
            HTTP client request object

        Returns
        -------
        Response
            Bearer token
        """

    @abstractmethod
    async def has_scope(self, token: str, permission: str) -> Any:
        """Check if a token has the permission scope.

        Parameters
        ----------
        token
            Auth token
        permission
            Permission string relevant for the provider

        Returns
        -------
        Any
            True if has permissions, otherwise False
        """

    @abstractmethod
    async def token_by_username_password(self, username: str, password: str) -> dict:
        """Get token via username and password. Should not be used in production.

        Parameters
        ----------
        username
            username or user
        password
            password of user

        Returns
        -------
        dict
            Structure containing tokens
        """

    @abstractmethod
    async def auth_callback(self, request: Request) -> str:
        """Call back from token_by_auth_flow.

        Parameters
        ----------
        request
            HTTP from Auth provider

        Returns
        -------
        str
            Bearer token
        """

    @abstractmethod
    async def validate_token(self, token: str):
        """Validate client session token/cookie."""


# pylint: disable=too-many-instance-attributes
class Keycloak(Provider):
    """Keycloak OIDC Provider."""

    def __init__(self):
        self.keycloak_url = os.environ["KEYCLOAK_URL"]
        self.redirect_url = os.environ["REDIRECT_URL"]
        self.realm = os.environ["REALM"]
        self.client_id = os.environ["CLIENT_ID"]
        self.client_secret = os.environ["CLIENT_SECRET"]
        self.state = os.environ["STATE"]

        self.kc = KeycloakOpenID(
            server_url=self.keycloak_url,
            client_id=self.client_id,
            realm_name=self.realm,
            client_secret_key=self.client_secret,
            verify=False,
        )

        self.uma = KeycloakUMA(connection=self.kc)

    @override
    async def token_by_username_password(self, username: str, password: str) -> dict:
        auth = await self.kc.a_token(username, password)
        return auth

    @override
    async def has_scope(self, token: str, permission: str) -> Any:
        return await self.kc.a_has_uma_access(token, permission)

    @override
    async def token_by_auth_flow(self, request: Request) -> Response:
        auth_url = await self.kc.a_auth_url(
            redirect_uri=self.redirect_url,
            scope="basic profile openid uma_authorization",
            state=self.state,
        )
        return RedirectResponse(auth_url)

    @override
    async def auth_callback(self, request: Request) -> str:
        code = request.query_params["code"]
        state = request.query_params["state"]
        if state != self.state:
            raise HTTPException(404, "Invalid state")

        access_token = await self.kc.a_token(
            grant_type=["authorization_code"], code=code, redirect_uri=self.redirect_url
        )

        return access_token["access_token"]

    async def _check_token(self, token: str):
        """Check if client can access endpoint based on token and permissions."""
        try:
            return await self.kc.a_userinfo(token)
        except KeycloakAuthenticationError as e:
            raise HTTPException(403, "Permissions error") from e
        except Exception as e:
            raise HTTPException(401, "Token error") from e

    @override
    async def validate_token(self, token: str):
        await self._check_token(token)


class Entra(Provider):
    """MS Entra OIDC Provider."""

    def __init__(self):
        self.tenant_id = os.environ["TENANT_ID"]
        self.client_id = os.environ["CLIENT_ID"]
        self.client_cred = os.environ["CLIENT_CRED"]
        self.redirect_url = os.environ["REDIRECT_URL"]
        scope = os.environ.get("SCOPES", "")
        self.scope = scope.strip().split(",")

        m_cache = msal.TokenCache()
        self.entra = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_cred,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            token_cache=m_cache,
        )

        response = requests.get(
            "https://login.microsoftonline.com/common/discovery/keys", timeout=60
        )
        self.keys = response.json()["keys"]

    @override
    async def token_by_auth_flow(self, request: Request) -> Response:
        loop = asyncio.get_running_loop()
        auth_url = await loop.run_in_executor(
            None,
            partial(
                self.entra.get_authorization_request_url,
                scopes=self.scope,
                redirect_uri=self.redirect_url,
            ),
        )

        return RedirectResponse(auth_url)

    @override
    async def token_by_username_password(self, username: str, password: str) -> dict:
        raise HTTPException(404, "Not implemented")

    @override
    async def has_scope(self, token: str, permission: str):
        raise HTTPException(404, "Not implemented")

    @override
    async def auth_callback(self, request: Request) -> str:
        code = request.query_params.get("code", None)
        if code is None:
            raise HTTPException(403, "code not found")

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                partial(
                    self.entra.acquire_token_by_authorization_code,
                    code=code,
                    scopes=self.scope,
                    redirect_uri=self.redirect_url,
                ),
            )

            if "access_token" not in result:
                raise HTTPException(403, "can not obtain token")
            return result["access_token"]

        # pylint: disable=raise-missing-from
        except Exception as e:
            logging.exception("auth_callback")
            raise HTTPException(status_code=403, detail=str(e))

    async def _check_token(self, token: str):
        token_headers = jwt.get_unverified_header(token)
        token_alg = token_headers["alg"]
        token_kid = token_headers["kid"]
        public_key = None
        for key in self.keys:
            if key["kid"] == token_kid:
                public_key = key

        rsa_pem_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(public_key))
        rsa_pem_key_bytes = rsa_pem_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        # Ignoring expiry date. This may be an issue if the state of the user changes
        decoded_token = jwt.decode(
            token,
            key=rsa_pem_key_bytes,
            verify_signature=True,
            options={"verify_exp": False},
            algorithms=[token_alg],
            audience=[self.client_id],
            issuer=f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",
        )
        return decoded_token

    @override
    async def validate_token(self, token: str):
        await self._check_token(token)


# Turn on Authentication = 1, Turn off = 0
AUTH = bool(int(os.getenv("AUTH", "1")))

# Keycloak (KC) or ENTRA
ENV_PROVIDER = os.getenv("PROVIDER", "KC")

PROVIDER = None
if ENV_PROVIDER == "KC":
    PROVIDER = Keycloak()
elif ENV_PROVIDER == "ENTRA":
    PROVIDER = Entra()
else:
    raise ValueError("Unknown Provider")

ingest_client = httpx.AsyncClient(base_url=os.getenv("INGEST_CLIENT", "http://localhost:8001"))
requests_client = httpx.AsyncClient(base_url=os.getenv("REQUESTS_CLIENT", "http://localhost:8002"))
storage_client = httpx.AsyncClient(base_url=os.getenv("STORAGE_CLIENT", "http://localhost:8003"))
migration_client = httpx.AsyncClient(
    base_url=os.getenv("MIGRATION_CLIENT", "http://localhost:8004")
)

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    SessionMiddleware, secret_key=os.getenv("COOKIE_SECRET", "this_is_a_secret"), max_age=None
)
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("./cert.pem", keyfile="./key.pem")


@app.get("/token_by_auth_flow")
async def token_by_auth_flow(request: Request):
    """Redirect to IDP for user authorisation."""
    # Get Code With Oauth Authorization Request
    return await PROVIDER.token_by_auth_flow(request)


@app.get("/auth_callback")
async def auth_callback(request: Request):
    """Auth callback from Provider."""
    return await PROVIDER.auth_callback(request)


@app.get("/heartbeat")
async def heartbeat():
    """Endpoint to check if Gateway is contactable."""
    return "ACK"


@app.get("/token_by_username_password")
async def token_by_username_password(username: str, password: str) -> dict:
    """Get OAUTH token based on username and password."""
    return await PROVIDER.token_by_username_password(username, password)


@app.get("/scope")
async def has_scope(token: str, permission: str):
    """Get UMA scopes."""
    return await PROVIDER.has_scope(token, permission)


async def _send_endpoint(url: httpx.URL, auth: dict, request: Request):
    client = None
    if request.url.path.startswith("/request"):
        client = requests_client
    elif request.url.path.startswith("/ingest"):
        client = ingest_client
    elif request.url.path.startswith("/storage"):
        client = storage_client
    elif request.url.path.startswith("/migration"):
        client = migration_client
    else:
        raise HTTPException(status_code=404, detail="Unknown endpoint")

    headers = request.headers.mutablecopy()
    if auth:
        headers["Authorization"] = f"Bearer {auth}"

    rp_req = client.build_request(
        request.method, url, headers=headers.raw, content=await request.body()
    )

    logger.info("send endpoint: %s", rp_req)
    return await client.send(rp_req, stream=True)


async def _reverse_proxy(request: Request):
    """Proxy client requests and check permissions based on token."""
    url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))

    auth = None
    if AUTH is True:
        auth = request.headers.get("authorization", None)
        if not auth:
            raise HTTPException(401, "No authorization header")
        try:
            bearer_token = auth.split(" ")[1]
        # pylint: disable=raise-missing-from
        except Exception:
            raise HTTPException(401, "Invalid getting auth")

        await PROVIDER.validate_token(bearer_token)

    try:
        rp_resp = await _send_endpoint(url, bearer_token, request)

        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=rp_resp.headers,
            background=BackgroundTask(rp_resp.aclose),
        )
    # pylint: disable=raise-missing-from
    except Exception as e:
        raise HTTPException(500, str(e))


app.add_route("/request/{path:path}", _reverse_proxy, ["GET", "POST", "PATCH"])
app.add_route("/storage/{path:path}", _reverse_proxy, ["GET", "POST"])
app.add_route("/ingest/{path:path}", _reverse_proxy, ["GET", "POST"])
app.add_route("/migration/{path:path}", _reverse_proxy, ["GET", "POST"])
