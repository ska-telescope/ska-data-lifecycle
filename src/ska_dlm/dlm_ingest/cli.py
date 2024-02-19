"""CLI support for dlm_ingest package."""
from requests import HTTPError
import typer
from rich import print as rich_print

from ska_dlm.dlm_db.db_access import DBQueryError

from . import dlm_ingest_requests
from .. import exceptions

app = typer.Typer()


@app.command()
# pylint: disable-next=missing-function-docstring
def ingest_data_item(  # noqa: D103
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
):
    try:
        rich_print(dlm_ingest_requests.register_data_item(item_name, uri, storage_name, storage_id))
    except (HTTPError, exceptions.ValueAlreadyInDB, exceptions.UnmetPreconditionForOperation, DBQueryError) as e:
        rich_print(f"[bold red]ERROR![/bold red]: {e}")

@app.command()
# pylint: disable-next=missing-function-docstring
def register_data_item(  # noqa: D103
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
):
    try:
        rich_print(HTTPError, dlm_ingest_requests.register_data_item(item_name, uri, storage_name, storage_id))
    except (exceptions.ValueAlreadyInDB, exceptions.UnmetPreconditionForOperation, DBQueryError) as e:
        rich_print(f"[bold red]ERROR![/bold red]: {e}")


