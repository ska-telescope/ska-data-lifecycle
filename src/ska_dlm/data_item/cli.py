"""CLI support for dlm_storage package."""


import typer

from ska_dlm import data_item
from ska_dlm.cli_utils import add_as_typer_command

cli_app = typer.Typer()
add_as_typer_command(cli_app, data_item.set_state)
add_as_typer_command(cli_app, data_item.set_uri)
add_as_typer_command(cli_app, data_item.set_uid_expiration)
add_as_typer_command(cli_app, data_item.set_oid_expiration)

if __name__ == "__main__":
    cli_app()