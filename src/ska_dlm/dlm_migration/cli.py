"""CLI support for dlm_ingest package."""
from requests import HTTPError
import typer
from rich import print as rich_print

from ska_dlm.dlm_db.db_access import DBQueryError

from . import dlm_migration_requests
from .. import exceptions

app = typer.Typer()


@app.command()
# pylint: disable-next=missing-function-docstring
def copy_data_item(  # noqa: D103
    item_name: str, destination_name: str
):
    try:
        rich_print(dlm_migration_requests.copy_data_item(item_name=item_name, destination_name=destination_name ))
    except (HTTPError, exceptions.ValueAlreadyInDB, exceptions.UnmetPreconditionForOperation, DBQueryError) as e:
        rich_print(f"[bold red]ERROR![/bold red]: {e}")
        raise e


