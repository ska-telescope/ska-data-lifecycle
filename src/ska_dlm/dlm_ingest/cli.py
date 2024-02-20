"""CLI support for dlm_ingest package."""
import functools

import typer
from requests import HTTPError
from rich import print as rich_print

from ska_dlm import dlm_ingest
from ska_dlm.dlm_db.db_access import DBQueryError

from .. import exceptions
from . import dlm_ingest_requests

app = typer.Typer()


@app.command()
@functools.wraps(dlm_ingest.ingest_data_item)
# pylint: disable-next=missing-function-docstring
def ingest_data_item(  # noqa: D103
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
):
    try:
        rich_print(
            dlm_ingest_requests.register_data_item(item_name, uri, storage_name, storage_id)
        )
    except (
        HTTPError,
        exceptions.ValueAlreadyInDB,
        exceptions.UnmetPreconditionForOperation,
        DBQueryError,
    ) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(dlm_ingest.ingest_data_item)
# pylint: disable-next=missing-function-docstring
def register_data_item(  # noqa: D103
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
):
    try:
        rich_print(dlm_ingest_requests.ingest_data_item(item_name, uri, storage_name, storage_id))
    except (
        HTTPError,
        exceptions.ValueAlreadyInDB,
        exceptions.UnmetPreconditionForOperation,
        DBQueryError,
    ) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")
