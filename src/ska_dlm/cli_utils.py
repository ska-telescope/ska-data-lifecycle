"""Common utilities for CLI modules."""

import copy
import functools
import inspect
import re
import typing

import typer
from docstring_parser import Docstring, parse
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
            func(*args, **kwargs)
        except Exception as ex:
            if isinstance(ex, tuple(exceptions_to_handle)):
                full_msg = ", caused by: ".join(f"{ex}" for ex in _exception_chain(ex))
                rich_print(f"[bold red]ERROR![/bold red]: {full_msg}")
                raise typer.Exit(1)
            raise

    app.command()(typer_docstring(func))


PARAGRAPH_RE = re.compile(r"(.)\n(?!\n)")


def typer_docstring(func: typing.Callable) -> typing.Callable:
    """A decorator that generates typer docs from the function signature and docstring.

    Parameters
    ----------
    func : typing.Callable
        Typer compatible function signature.

    Returns
    -------
    typing.Callable
        Decorated function with updated annotations and docstring.
    """
    # Collect information about the parameters of the function
    parameters: dict[str, dict] = {}
    kinds: dict[str, type] = {}

    # Parse signature first so all parameter names are populated
    signature = inspect.signature(func)
    for arg_name, param in signature.parameters.items():
        parameters[arg_name] = {}
        kinds[arg_name] = (
            typer.models.ArgumentInfo
            if param.default is inspect.Signature.empty
            else typer.models.OptionInfo
        )

    # Parse docstring
    assert func.__doc__
    docstring: Docstring = parse(func.__doc__)

    # extract as help messages from docstring (if present)
    for par in docstring.params:
        if par.arg_name in parameters:
            parameters[par.arg_name]["help"] = par.description

    def create_param(
        kind: type,
        **param_kwargs,
    ) -> typer.models.ParameterInfo:
        match kind:
            case typer.models.ArgumentInfo:
                return typer.Argument(**param_kwargs, show_default=False)
            case _:
                return typer.Option(**param_kwargs)

    # Transform the parameters into info instances
    docstring_infos: dict[str, typer.models.ParameterInfo] = {
        arg_name: create_param(kinds[arg_name], **param_kwargs)
        for arg_name, param_kwargs in parameters.items()
    }

    output_annotations: dict = {}
    for arg_name, info in docstring_infos.items():
        updated_annotation: type | typing.Annotated = copy.deepcopy(func.__annotations__[arg_name])
        if hasattr(updated_annotation, "__metadata__"):
            updated = False
            for meta in updated_annotation.__metadata__:
                if isinstance(meta, typer.models.ParameterInfo):
                    # override missing help with docstring
                    if meta.help is None:
                        meta.help = copy.deepcopy(info.help)

                    updated = True
            if not updated:
                # annotations found but not for typer
                updated_annotation.__metadata__ += (info,)
        else:
            # create annotation
            # NOTE:
            updated_annotation = typing.Annotated[updated_annotation, info]
        output_annotations[arg_name] = updated_annotation

    if "return" in output_annotations:
        output_annotations["return"] = func.__annotations__["return"]

    func.__annotations__ = output_annotations

    # Only keep the main description as docstring so the CLI won't print
    # the whole docstring, including the parameters
    func.__doc__ = "\n\n".join(
        [
            docstring.short_description or "",
            PARAGRAPH_RE.sub(r"\1 ", docstring.long_description or ""),
        ]
    )

    return func
