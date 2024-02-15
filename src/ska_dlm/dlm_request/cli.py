"""CLI support for dlm_storage package."""

import typer
from rich import print as rich_print

from . import dlm_request_requests

app = typer.Typer()


@app.command()
# pylint: disable-next=missing-function-docstring
def query_data_item(item_name: str = "", oid: str = "", uid: str = ""):  # noqa: D103
    rich_print(dlm_request_requests.query_data_item(item_name, oid, uid))
