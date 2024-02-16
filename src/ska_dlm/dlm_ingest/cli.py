"""CLI support for dlm_ingest package."""
import typer
from rich import print as rich_print

from . import dlm_ingest_requests

app = typer.Typer()


@app.command()
# pylint: disable-next=missing-function-docstring
def ingest_data_item(  # noqa: D103
    item_name: str, uri: str = "", storage_name: str = "", storage_id: str = ""
):
    rich_print(dlm_ingest_requests.ingest_data_item(item_name, uri, storage_name, storage_id))
