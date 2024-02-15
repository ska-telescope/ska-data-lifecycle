"""CLI support for dlm_storage package."""
import functools

import typer
from rich import print as rich_print

from . import dlm_storage_requests

app = typer.Typer()


@app.command()
@functools.wraps(dlm_storage_requests.init_location)
# pylint: disable-next=missing-function-docstring
def init_location(  # noqa: D103
    location_name: str = "",
    location_type: str = "",
    location_country: str = "",
    location_city: str = "",
    location_facility: str = "",
):
    rich_print(
        dlm_storage_requests.init_location(
            location_name, location_type, location_country, location_city, location_facility
        )
    )


@app.command()
# pylint: disable-next=missing-function-docstring,too-many-arguments
def init_storage(  # noqa: D103
    storage_name: str = "",
    location_name: str = "",
    location_id: str = "",
    storage_type: str = "",
    storage_interface: str = "",
    storage_capacity: int = -1,
    json_data: str = "",
):
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
