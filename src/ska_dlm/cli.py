"""CLI support for ska_dlm package."""

import logging

import ska_ser_logging
from requests import HTTPError

from ska_dlm.cli_utils import dump_short_stacktrace
from ska_dlm.dlm_db.db_access import DBQueryError
from ska_dlm.error_handling_typer import ErrorHandlingTyper
from ska_dlm.exceptions import UnmetPreconditionForOperation

from .data_item.cli import app as item_app
from .dlm_ingest.cli import app as ingest_app
from .dlm_migration.cli import app as migration_app
from .dlm_request.cli import app as request_app
from .dlm_storage.cli import app as storage_app

app = ErrorHandlingTyper(pretty_exceptions_show_locals=False)
app.add_typer(ingest_app, name="ingest", help="Ingest data items")
app.add_typer(item_app, name="data-item", help="Manage data_item information")
app.add_typer(request_app, name="request", help="Request queries")
app.add_typer(storage_app, name="storage", help="Manage storage and location information")
app.add_typer(migration_app, name="migration", help="Manage storage and location information")


app.error_handler(HTTPError)(dump_short_stacktrace)
app.error_handler(DBQueryError)(dump_short_stacktrace)
app.error_handler(UnmetPreconditionForOperation)(dump_short_stacktrace)


def main():
    """SKA Data Lifecycle Management command-line utility."""
    ska_ser_logging.configure_logging(level=logging.INFO)
    app()


if __name__ == "__main__":
    main()
