"""CLI support for dlm_ingest package."""
import typer

from ska_dlm.cli_utils import add_as_typer_command

from .. import exceptions
from . import dlm_migration_requests

app = typer.Typer()
add_as_typer_command(
    app, dlm_migration_requests.copy_data_item, include_excs=[exceptions.ValueAlreadyInDB]
)
