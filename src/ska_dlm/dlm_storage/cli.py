"""CLI support for dlm_storage package."""

import functools

import typer
from requests import HTTPError
from rich import print as rich_print

from ska_dlm.dlm_db.db_access import DBQueryError
from ska_dlm.exceptions import UnmetPreconditionForOperation

from . import dlm_storage_requests

app = typer.Typer()


@app.command()
@functools.wraps(dlm_storage_requests.init_location)
def init_location(  # noqa: D103, pylint: disable=C0116
    location_name: str = "",
    location_type: str = "",
    location_country: str = "",
    location_city: str = "",
    location_facility: str = "",
):
    try:
        rich_print(
            dlm_storage_requests.init_location(
                location_name, location_type, location_country, location_city, location_facility
            )
        )
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
# @functools.wraps(dlm_storage_requests.init_storage)
def init_storage(  # noqa: D103, pylint: disable=R0913,C0116
    storage_name: str = "",
    location_name: str = "",
    location_id: str = "",
    storage_type: str = "",
    storage_interface: str = "",
    storage_capacity: int = -1,
    json_data: str = "",
):
    try:
        rich_print(
            dlm_storage_requests.init_storage(
                storage_name,
                location_name,
                location_id,
                storage_type,
                storage_interface,
                storage_capacity,
                json_data,
            )
        )
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(dlm_storage_requests.query_storage)
def query_storage(  # noqa: D103, pylint: disable=C0116
    storage_name: str = "", storage_id: str = ""
):
    try:
        rich_print(
            dlm_storage_requests.query_storage(storage_name=storage_name, storage_id=storage_id)
        )
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(dlm_storage_requests.query_location)
def query_location(  # noqa: D103, pylint: disable=C0116
    location_name: str = "", location_id: str = ""
):
    try:
        rich_print(dlm_storage_requests.query_location(location_name, location_id))
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(dlm_storage_requests.create_storage_config)
def create_storage_config(  # noqa: D103, pylint: disable=C0116
    storage_name: str = "", storage_id: str = "", config: str = "", config_type="rclone"
):  # noqa: D103
    try:
        rich_print(
            dlm_storage_requests.create_storage_config(
                storage_name=storage_name,
                storage_id=storage_id,
                config=config,
                config_type=config_type,
            )
        )
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")


@app.command()
@functools.wraps(dlm_storage_requests.get_storage_config)
def get_storage_config(  # noqa: D103, pylint: disable=C0116
    storage_name: str = "", storage_id: str = "", config_type: str = "rclone"
):
    try:
        rich_print(
            dlm_storage_requests.get_storage_config(
                storage_name=storage_name, storage_id=storage_id, config_type=config_type
            )
        )
    except (HTTPError, UnmetPreconditionForOperation, DBQueryError) as error:
        rich_print(f"[bold red]ERROR![/bold red]: {error}")
