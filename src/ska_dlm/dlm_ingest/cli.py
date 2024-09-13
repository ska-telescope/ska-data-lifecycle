"""CLI support for dlm_ingest package."""

from ska_dlm import dlm_ingest
from ska_dlm.cli_utils import add_as_typer_command, dump_short_stacktrace
from ska_dlm.error_handling_typer import ErrorHandlingTyper

from .. import exceptions

app = ErrorHandlingTyper()
app.error_handler(exceptions.ValueAlreadyInDB)(dump_short_stacktrace)

add_as_typer_command(app, dlm_ingest.register_data_item)
