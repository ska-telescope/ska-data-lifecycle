"""API Gateway"""

import logging
import os

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from keycloak import KeycloakOpenID, KeycloakUMA
from keycloak.exceptions import KeycloakAuthenticationError
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

KEYCLOAK_URL = os.environ["KEYCLOAK_URL"]
REDIRECT_URL = os.environ["REDIRECT_URL"]
REALM = os.environ["REALM"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
STATE = os.environ["STATE"]

AUTH = bool(int(os.environ["AUTH"]))

ingest_client = httpx.AsyncClient(base_url=os.environ["INGEST_CLIENT"])
requests_client = httpx.AsyncClient(base_url=os.environ["REQUESTS_CLIENT"])
storage_client = httpx.AsyncClient(base_url=os.environ["STORAGE_CLIENT"])
migration_client = httpx.AsyncClient(base_url=os.environ["MIGRATION_CLIENT"])


# Configure client
keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_URL,
    client_id=CLIENT_ID,
    realm_name=REALM,
    client_secret_key=CLIENT_SECRET,
    verify=False,
)

keycloak_uma = KeycloakUMA(connection=keycloak_openid)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SKA-DLM: Test API Gateway REST I/F",
    description="The REST calls accepted by the SKA-DLM test API gateway."   
)


@app.get("/login")
async def login():
    """Redirect to IDP for user authorisation"""
    # Get Code With Oauth Authorization Request
    auth_url = await keycloak_openid.a_auth_url(
        redirect_uri=REDIRECT_URL, scope="basic profile openid uma_authorization", state=STATE
    )
    return RedirectResponse(auth_url)


@app.get("/auth_callback")
async def auth_callback(request: Request):
    """Called when user gives authorisation. Swap a code for token"""
    code = request.query_params["code"]
    state = request.query_params["state"]
    if state != STATE:
        raise HTTPException("Invalid state")

    access_token = await keycloak_openid.a_token(
        grant_type=["authorization_code"], code=code, redirect_uri=REDIRECT_URL
    )

    return access_token["access_token"]


@app.get("/heartbeat")
async def heartbeat():
    """Endpoint to check if Gateway is contactable"""
    return "ACK"


# pylint: disable=redefined-outer-name
@app.get("/token")
async def token(username: str, password: str):
    """Get OAUTH token based on username and password"""
    access_token = keycloak_openid.token(username, password)
    return access_token["access_token"]


@app.get("/scope")
async def has_scope(token: str, permission: str):
    """Get UMA scopes"""
    return keycloak_openid.has_uma_access(token, permission)


# pylint: disable=redefined-outer-name
async def _check_permissions(token: str, request: Request):
    """Check is client can access endpoint based on token and permissions"""
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
    # Check with permissions services if the user has permission to access endpoint
    await keycloak_openid.a_uma_permissions(token, f"{res}#{scope}")


async def _send_endpoint(url: httpx.URL, request: Request):
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
        raise HTTPException("Unknown endpoint")

    rp_req = client.build_request(
        request.method, url, headers=request.headers.raw, content=await request.body()
    )
    logger.info("send endpoint: %s", rp_req)
    return await client.send(rp_req, stream=True)


async def _reverse_proxy(request: Request):
    """Proxy client requests and check permissions based on token"""
    url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))

    if AUTH is True:
        auth = request.headers.get("authorization", None)
        if not auth:
            raise HTTPException(401, "No authorization header")
        try:
            bearer_token = auth.split(" ")[1]
            await _check_permissions(bearer_token, request)
        except KeycloakAuthenticationError as e:
            raise HTTPException(403, "Permissions error") from e
        except Exception as e:
            raise HTTPException(401, "Token error") from e

    rp_resp = await _send_endpoint(url, request)

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
