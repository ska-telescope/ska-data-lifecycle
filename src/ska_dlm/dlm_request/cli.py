"""CLI support for dlm_storage package."""
import typer

from ska_dlm.cli_utils import add_as_typer_command

from . import dlm_request_requests

app = typer.Typer()
add_as_typer_command(app, dlm_request_requests.query_data_item)
add_as_typer_command(app, dlm_request_requests.query_new)
