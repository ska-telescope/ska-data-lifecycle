"""CLI support for dlm_storage package."""

import typer
from rich import print as rich_print

from . import data_item_requests

app = typer.Typer()


@app.command()
# pylint: disable-next=missing-function-docstring
def set_state(uid: str = "", state: str = ""):  # noqa: D103
    rich_print(data_item_requests.set_state(uid, state))


@app.command()
# pylint: disable-next=missing-function-docstring
def set_uri(uid: str = "", uri: str = "", storage_id: str = ""):  # noqa: D103
    rich_print(data_item_requests.set_uri(uid, uri, storage_id))
