"""CLI support for dlm_storage package."""

import typer
from ska_dlm.cli_utils import add_as_typer_command

from . import dlm_storage_requests

cli_app = typer.Typer()
add_as_typer_command(cli_app, dlm_storage_requests.init_location)
add_as_typer_command(cli_app, dlm_storage_requests.init_storage)
add_as_typer_command(cli_app, dlm_storage_requests.query_storage)
add_as_typer_command(cli_app, dlm_storage_requests.query_location)
add_as_typer_command(cli_app, dlm_storage_requests.create_storage_config)
add_as_typer_command(cli_app, dlm_storage_requests.get_storage_config)

if __name__ == "__main__":
    cli_app()