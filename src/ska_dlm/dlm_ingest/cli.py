"""CLI support for dlm_ingest package."""
import typer

from ska_dlm import dlm_ingest
from ska_dlm.cli_utils import add_as_typer_command

from .. import exceptions

app = typer.Typer()
add_as_typer_command(
    app, dlm_ingest.register_data_item, include_excs=[exceptions.ValueAlreadyInDB]
)
