"""CLI support for dlm_storage package."""

from urllib.error import HTTPError
import typer
from rich import print as rich_print

from ska_dlm.dlm_db.db_access import DBQueryError
from ska_dlm.exceptions import UnmetPreconditionForOperation

from . import dlm_request_requests

app = typer.Typer()


@app.command()
# pylint: disable-next=missing-function-docstring
def query_data_item(item_name: str = "", oid: str = "", uid: str = ""):  # noqa: D103
    try:
        rich_print(dlm_request_requests.query_data_item(item_name, oid, uid))
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as e:
        rich_print(f"[bold red]ERROR![/bold red]: {e}")
