"""Common utilities for CLI modules."""

import functools
import typing

import typer
from requests import HTTPError
from rich import print as rich_print

from ska_dlm.dlm_db.db_access import DBQueryError
from ska_dlm.exceptions import UnmetPreconditionForOperation


def _exception_chain(ex: Exception):
    while ex:
        yield ex
        ex = ex.__cause__


def add_as_typer_command(
    app: typer.Typer,
    func: typing.Callable,
    include_excs: typing.Iterable[type[Exception]] | None = None,
    exclude_excs: typing.Iterable[type[Exception]] | None = None,
):
    """
    Add a typer command for the given callable function.

    The result of invoking the function is printed onto the screen. Certain exceptions are
    summarised in a single line instead of resulting on a full stack trace. Users can add/remove
    exceptions from getting this special treatment.

    Parameters
    ----------
    app : typer.Typer
        _description_
    func : typing.Callable
        _description_
    include_excs : typing.Iterable[type[Exception]] | None, optional
        _description_, by default None
    exclude_excs : typing.Iterable[type[Exception]] | None, optional
        _description_, by default None
    """
    exceptions_to_handle = {HTTPError, DBQueryError, UnmetPreconditionForOperation}
    exceptions_to_handle.update(set(include_excs or []))
    exceptions_to_handle.difference_update(set(exclude_excs or []))

    @functools.wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            rich_print(func(*args, **kwargs))
        except Exception as ex:
            if isinstance(ex, tuple(exceptions_to_handle)):
                full_msg = ", caused by: ".join(f"{ex}" for ex in _exception_chain(ex))
                rich_print(f"[bold red]ERROR![/bold red]: {full_msg}")
                raise typer.Exit(1)
            raise

    app.command()(_wrapper)
