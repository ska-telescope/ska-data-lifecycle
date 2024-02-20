"""CLI support for dlm_storage package."""

import functools

import typer
from requests import HTTPError
from rich import print as rich_print

from ska_dlm import data_item
from ska_dlm.dlm_db.db_access import DBQueryError
from ska_dlm.exceptions import UnmetPreconditionForOperation

from . import data_item_requests

app = typer.Typer()


@app.command()
@functools.wraps(data_item.set_state)
# pylint: disable-next=missing-function-docstring
def set_state(uid: str = "", state: str = ""):  # noqa: D103
    try:
        rich_print(data_item_requests.set_state(uid, state))
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(data_item.set_uri)
# pylint: disable-next=missing-function-docstring
def set_uri(uid: str = "", uri: str = "", storage_id: str = ""):  # noqa: D103
    try:
        rich_print(data_item_requests.set_uri(uid, uri, storage_id))
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(data_item.set_uid_expiration)
# pylint: disable-next=missing-function-docstring
def set_uid_expiration(uid: str, expiration: str):  # noqa: D103
    try:
        rich_print(data_item_requests.set_uid_expiration(uid, expiration))
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(data_item.set_oid_expiration)
# pylint: disable-next=missing-function-docstring
def set_oid_expiration(oid: str, expiration: str):  # noqa: D103
    try:
        rich_print(data_item_requests.set_oid_expiration(oid, expiration))
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")
