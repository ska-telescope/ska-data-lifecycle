"""CLI support for dlm_ingest package."""
import typer
from requests import HTTPError
from rich import print as rich_print

from ska_dlm.dlm_db.db_access import DBQueryError

from .. import exceptions
from . import dlm_migration_requests

app = typer.Typer()


@app.command()
# pylint: disable-next=missing-function-docstring
def copy_data_item(item_name: str, destination_name: str):  # noqa: D103
    try:
        rich_print(
            dlm_migration_requests.copy_data_item(
                item_name=item_name, destination_name=destination_name
            )
        )
    except (
        HTTPError,
        exceptions.ValueAlreadyInDB,
        exceptions.UnmetPreconditionForOperation,
        DBQueryError,
    ) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")
        raise error
