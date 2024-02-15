"""CLI support for ska_dlm package."""
import logging

import typer

from .dlm_ingest.cli import app as ingest_app
from .dlm_storage.cli import app as storage_app

logger = logging.getLogger(__name__)

app = typer.Typer(pretty_exceptions_show_locals=False)
app.add_typer(ingest_app, name="ingest", help="Ingest data items")
app.add_typer(storage_app, name="storage", help="Manage storage and location information")


def main():
    """SKA Data Lifecycle Management command-line utility."""
    app()


if __name__ == "__main__":
    main()
