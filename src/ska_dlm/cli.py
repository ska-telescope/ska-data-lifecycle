"""
CLI support for ska_dlm package.

The SKA DLM is using typer to provide a convenient user experience
on the command line, including help and command completion. After
installation of the package it can be used with the command:

```bash
$ ska-dlm
Usage: ska-dlm [OPTIONS] COMMAND [ARGS]...
Try 'ska-dlm --help' for help.
```
"""

import logging

import ska_ser_logging
from requests import HTTPError

from ska_dlm.dlm_db.db_access import DBQueryError
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.exceptions import UnmetPreconditionForOperation
from ska_dlm.typer_utils import dump_short_stacktrace

from .data_item.data_item_requests import cli as item_app
from .dlm_ingest.dlm_ingest_requests import cli as ingest_app
from .dlm_migration.dlm_migration_requests import cli as migration_app
from .dlm_request.dlm_request_requests import cli as request_app
from .dlm_storage.dlm_storage_requests import cli as storage_app

app = ExceptionHandlingTyper(pretty_exceptions_show_locals=False, result_callback=print)
app.add_typer(ingest_app, name="ingest", help="Ingest data items")
app.add_typer(item_app, name="data-item", help="Manage data_item information")
app.add_typer(request_app, name="request", help="Request queries")
app.add_typer(storage_app, name="storage", help="Manage storage and location information")
app.add_typer(migration_app, name="migration", help="Manage data movement and migration")


app.exception_handler(HTTPError)(dump_short_stacktrace)
app.exception_handler(DBQueryError)(dump_short_stacktrace)  # TODO YAN-XXXX: Read message from body
app.exception_handler(UnmetPreconditionForOperation)(dump_short_stacktrace)


def main():
    """SKA Data Lifecycle Management command-line utility."""
    ska_ser_logging.configure_logging(level=logging.INFO)
    app()


if __name__ == "__main__":
    main()
