"""CLI support for dlm_storage package."""
from fastapi import FastAPI
import typer

from ska_dlm.cli_utils import add_as_typer_command

from . import dlm_request_requests

cli_app = typer.Typer()
add_as_typer_command(cli_app, dlm_request_requests.query_data_item)
add_as_typer_command(cli_app, dlm_request_requests.query_new)

if __name__ == "__main__":
    cli_app()
