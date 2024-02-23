"""CLI support for dlm_storage package."""
import typer

from ska_dlm.cli_utils import add_as_typer_command

from . import dlm_storage_requests

app = typer.Typer()
add_as_typer_command(app, dlm_storage_requests.init_location)
add_as_typer_command(app, dlm_storage_requests.init_storage)
add_as_typer_command(app, dlm_storage_requests.query_storage)
add_as_typer_command(app, dlm_storage_requests.query_location)
add_as_typer_command(app, dlm_storage_requests.create_storage_config)
add_as_typer_command(app, dlm_storage_requests.get_storage_config)
