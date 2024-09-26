"""API Gateway"""

import asyncio
import json
import logging
import os
import ssl
from urllib.request import urlopen

import httpx
import jwt
import msal
import requests
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from keycloak import KeycloakOpenID, KeycloakUMA
from keycloak.exceptions import KeycloakAuthenticationError
from starlette.background import BackgroundTask
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import StreamingResponse


class Provider:
    def __init__(self):
        pass

    async def token_by_auth_flow(self, request: Request):
        raise HTTPException(404, "Not implemented")

    async def has_scope(self, token: str, permission: str):
        raise HTTPException(404, "Not implemented")

    async def token_by_username_password(self, username: str, password: str):
        raise HTTPException(404, "Not implemented")

    async def auth_callback(self, request: Request):
        raise HTTPException(404, "Not implemented")

    async def start_session(self, token: str, request: Request):
        raise HTTPException(404, "Not implemented")

    async def end_session(self, request: Request):
        raise HTTPException(404, "Not implemented")

    async def validate_token(request: Request):
        raise HTTPException(404, "Not implemented")


class Keycloak(Provider):
    def __init__(self):
        self.KEYCLOAK_URL = os.environ["KEYCLOAK_URL"]
        self.REDIRECT_URL = os.environ["REDIRECT_URL"]
        self.REALM = os.environ["REALM"]
        self.CLIENT_ID = os.environ["CLIENT_ID"]
        self.CLIENT_SECRET = os.environ["CLIENT_SECRET"]
        self.STATE = os.environ["STATE"]

        self.kc = KeycloakOpenID(
            server_url=self.KEYCLOAK_URL,
            client_id=self.CLIENT_ID,
            realm_name=self.REALM,
            client_secret_key=self.CLIENT_SECRET,
            verify=False,
        )

        self.uma = KeycloakUMA(connection=self.kc)

    async def token_by_username_password(self, username: str, password: str):
        print(username, password)
        access_token = await self.kc.a_token(username, password)
        return access_token["access_token"]

    async def has_scope(self, token: str, permission: str):
        return await self.kc.a_openid.has_uma_access(token, permission)

    async def token_by_auth_flow(self, request: Request):
        auth_url = await self.kc.a_auth_url(
            redirect_uri=self.REDIRECT_URL,
            scope="basic profile openid uma_authorization",
            state=self.STATE,
        )
        return RedirectResponse(auth_url)

    async def auth_callback(self, request: Request):
        code = request.query_params["code"]
        state = request.query_params["state"]
        if state != self.STATE:
            raise HTTPException(404, "Invalid state")

        access_token = await self.kc.a_token(
            grant_type=["authorization_code"], code=code, redirect_uri=self.REDIRECT_URL
        )

        return access_token["access_token"]

    async def start_session(self, token: str, request: Request):
        try:
            await self._check_token(token, Request)
            request.session["token"] = token
        except jwt.exceptions.PyJWTError as e:
            raise HTTPException(401, str(e))

    async def end_session(self, request: Request):
        request.session["token"] = None

    async def _check_token(self, token: str, request: Request):
        """Check is client can access endpoint based on token and permissions"""
        """
        path = request.url.path
        logger.info("checking permissions for: %s", request)
        if path.startswith("/request"):
            res = "res:request"
            scope = "scope:read"

        elif path.startswith("/ingest"):
            res = "res:ingest"
            scope = "scope:create"

        elif path.startswith("/storage"):
            res = "res:storage"

            action = path.split("/")[2]
            if action.startswith("query"):
                scope = "scope:read"
            else:
                scope = "scope:create"

        elif path.startswith("/migration"):
            res = "res:migraiton"
            scope = "scope:read"
        else:
            raise HTTPException("Unknown endpoint")
        """
        try:
            # Check with permissions services if the user has permission to access endpoint
            # await self.kc.a_uma_permissions(token, f"{res}#{scope}")
            return await self.kc.a_userinfo(token)
        except KeycloakAuthenticationError as e:
            raise HTTPException(403, "Permissions error") from e
        except Exception as e:
            raise HTTPException(401, "Token error") from e

    async def validate_token(self, request: Request):
        token = request.session.get("token")
        if not token:
            raise HTTPException(403, "Session token not found")
        return await self._check_token(token, request)


class Entra(Provider):
    def __init__(self):
        self.TENANT_ID = os.environ["TENANT_ID"]
        self.CLIENT_ID = os.environ["CLIENT_ID"]
        self.CLIENT_CRED = os.environ["CLIENT_CRED"]
        m_cache = msal.TokenCache()
        self.entra = msal.ConfidentialClientApplication(
            client_id=self.CLIENT_ID,
            client_credential=self.CLIENT_CRED,
            authority=f"https://login.microsoftonline.com/{self.TENANT_ID}",
            token_cache=m_cache,
        )

        response = requests.get("https://login.microsoftonline.com/common/discovery/keys")
        self.KEYS = response.json()["keys"]

    async def token_by_auth_flow(self, request: Request):
        loop = asyncio.get_running_loop()
        auth = await loop.run_in_executor(
            None,
            self.entra.initiate_auth_code_flow,
            [],
            "https://dlm-test.icrar.org/auth_callback",
        )
        request.session["flow"] = auth
        print(auth["auth_uri"])
        return RedirectResponse(auth["auth_uri"])

    async def auth_callback(self, request: Request):
        flow = request.session.get("flow", None)
        if not flow:
            raise HTTPException(403, "Unknown flow state")

        try:
            loop = asyncio.get_running_loop()
            access_token = await loop.run_in_executor(
                None, self.entra.acquire_token_by_auth_code_flow, flow, dict(request.query_params)
            )
            request.session["id_token"] = access_token["id_token"]
            return access_token["id_token"]
        except Exception as e:
            raise HTTPException(status_code=403, detail=str(e))

    async def start_session(self, token: str, request: Request):
        try:
            await self._check_token(token, Request)
            request.session["token"] = token
        except jwt.exceptions.PyJWTError as e:
            raise HTTPException(401, str(e))

    async def end_session(self, request: Request):
        request.session["token"] = None

    async def _check_token(self, token: str, request: Request):
        token_headers = jwt.get_unverified_header(token)
        token_alg = token_headers["alg"]
        token_kid = token_headers["kid"]
        public_key = None
        for key in self.KEYS:
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
            audience=[self.CLIENT_ID],
            issuer=f"https://login.microsoftonline.com/{self.TENANT_ID}/v2.0",
        )
        return decoded_token

    async def validate_token(self, request: Request):
        token = request.session.get("token")
        if not token:
            raise HTTPException(403, "Session token not found")
        return await self._check_token(token, request)


# Turn on Authentication = 1, Turn off = 0
AUTH = bool(int(os.getenv("AUTH", "1")))

# Keycloak (KC) or ENTRA
PROVIDER = os.getenv("PROVIDER", "KC")

provider = None
if PROVIDER == "KC":
    provider = Keycloak()
elif PROVIDER == "ENTRA":
    provider = Entra()

ingest_client = httpx.AsyncClient(base_url=os.getenv("INGEST_CLIENT", "http://localhost:8001"))
requests_client = httpx.AsyncClient(base_url=os.getenv("REQUESTS_CLIENT", "http://localhost:8002"))
storage_client = httpx.AsyncClient(base_url=os.getenv("STORAGE_CLIENT", "http://localhost:8003"))
migration_client = httpx.AsyncClient(
    base_url=os.getenv("MIGRATION_CLIENT", "http://localhost:8004")
)

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="some-random-string")
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("./cert.pem", keyfile="./key.pem")


@app.get("/token_by_auth_flow")
async def token_by_auth_flow(request: Request):
    """Redirect to IDP for user authorisation"""
    # Get Code With Oauth Authorization Request
    return await provider.token_by_auth_flow(request)


@app.get("/auth_callback")
async def auth_callback(request: Request):
    return await provider.auth_callback(request)


@app.post("/start_session", status_code=status.HTTP_200_OK)
async def session(request: Request):
    auth = request.headers.get("authorization", None)
    if not auth:
        raise HTTPException(401, "No authorization header")
    try:
        bearer_token = auth.split(" ")[1]
    except Exception as e:
        raise HTTPException(401, "Invalid authorization header")
    await provider.start_session(bearer_token, request)
    return {"Result": "OK"}


@app.post("/end_session", status_code=status.HTTP_200_OK)
async def end_session(request: Request):
    await provider.end_session(request)
    return {"Result": "OK"}


@app.get("/heartbeat")
async def heartbeat():
    """Endpoint to check if Gateway is contactable"""
    return "ACK"


# pylint: disable=redefined-outer-name
@app.get("/token_by_username_password")
async def token_by_username_password(username: str, password: str):
    """Get OAUTH token based on username and password"""
    return await provider.token_by_username_password(username, password)


@app.get("/scope")
async def has_scope(self, token: str, permission: str):
    """Get UMA scopes"""
    return await provider.has_scope(token, permission)


async def _send_endpoint(url: httpx.URL, id_token: dict, request: Request):
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
    headers["token"] = json.dumps(id_token)

    rp_req = client.build_request(
        request.method, url, headers=headers.raw, content=await request.body()
    )

    logger.info("send endpoint: %s", rp_req)
    return await client.send(rp_req, stream=True)


async def _reverse_proxy(request: Request):
    """Proxy client requests and check permissions based on token"""
    url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))

    if AUTH is True:
        id_token = await provider.validate_token(request)
    else:
        # if no AUTH is set then mock a user token
        id_token = {"name": "test", "preferred_username": "test@skao.it"}

    rp_resp = await _send_endpoint(url, id_token, request)

    return StreamingResponse(
        rp_resp.aiter_raw(),
        status_code=rp_resp.status_code,
        headers=rp_resp.headers,
        background=BackgroundTask(rp_resp.aclose),
    )


app.add_route("/request/{path:path}", _reverse_proxy, ["GET", "POST"])
app.add_route("/storage/{path:path}", _reverse_proxy, ["GET", "POST"])
app.add_route("/ingest/{path:path}", _reverse_proxy, ["GET", "POST"])
app.add_route("/migration/{path:path}", _reverse_proxy, ["GET", "POST"])
