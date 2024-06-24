"""CLI support for ska_dlm package."""

import logging

import ska_ser_logging
import typer

from .data_item.cli import cli_app as item_app
from .dlm_ingest.cli import cli_app as ingest_app
from .dlm_migration.cli import cli_app as migration_app
from .dlm_request.cli import cli_app as request_app
from .dlm_storage.cli import cli_app as storage_app

app = typer.Typer(pretty_exceptions_show_locals=False)
app.add_typer(ingest_app, name="ingest", help="Ingest data items")
app.add_typer(item_app, name="data-item", help="Manage data_item information")
app.add_typer(request_app, name="request", help="Request queries")
app.add_typer(storage_app, name="storage", help="Manage storage and location information")
app.add_typer(migration_app, name="migration", help="Manage storage and location information")


def main():
    """SKA Data Lifecycle Management command-line utility."""
    ska_ser_logging.configure_logging(level=logging.INFO)
    app()


if __name__ == "__main__":
    main()
