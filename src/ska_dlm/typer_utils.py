"""Common utilities for CLI modules."""

import copy
import inspect
import typing
from typing import ParamSpec, TypeVar

import typer
from docstring_parser import Docstring, parse
from rich import print as rich_print

ParamsT = ParamSpec("ParamsT")
ReturnT = TypeVar("ReturnT")


def _iterate_exception_causes(ex: Exception):
    while ex:
        yield ex
        ex = ex.__cause__


def dump_short_stacktrace(ex: Exception):
    """Register custom stacktrace print for DBQueryError."""
    full_msg = "\ncaused by: ".join(f"{ex}" for ex in _iterate_exception_causes(ex))
    rich_print(f"[bold red]ERROR![/bold red]: {full_msg}")
    return 1


def create_typer_parameter(
    kind: type,
    **param_kwargs,
) -> typer.models.ParameterInfo:
    """Create typer parameter from kwargs."""
    match kind:
        case typer.models.ArgumentInfo:
            return typer.Argument(**param_kwargs, show_default=False)
        case _:
            return typer.Option(**param_kwargs)


def create_typer_function_info(
    func: typing.Callable[ParamsT, ReturnT], doc: Docstring
) -> dict[str, typer.models.ParameterInfo]:
    """Create dictionary of default Typer annotations for a given function."""
    # Collect information about the parameters of the function
    kinds: dict[str, type] = {}
    parameters: dict[str, dict] = {}

    # Parse signature first so all parameter names are populated
    signature = inspect.signature(func)
    for arg_name, param in signature.parameters.items():
        parameters[arg_name] = {}
        kinds[arg_name] = (
            typer.models.ArgumentInfo
            if param.default is inspect.Signature.empty
            else typer.models.OptionInfo
        )

    # extract as help messages from docstring (if present)
    for par in doc.params:
        if par.arg_name in parameters:
            parameters[par.arg_name]["help"] = par.description

    # Transform the parameters into info instances
    docstring_infos: dict[str, typer.models.ParameterInfo] = {
        arg_name: create_typer_parameter(kinds[arg_name], **param_kwargs)
        for arg_name, param_kwargs in parameters.items()
    }
    return docstring_infos


def typer_docstring(func: typing.Callable[ParamsT, ReturnT]) -> typing.Callable[ParamsT, ReturnT]:
    """Decorator that generates Typer annotations from the function signature and docstring.

    NOTE: This does not modify the __doc__ member.

    Parameters
    ----------
    func : typing.Callable[ParamsT, T]
        Typer compatible function signature.

    Returns
    -------
    typing.Callable[ParamsT, T]
        Decorated function with updated annotations and docstring.
    """
    # Parse docstring
    assert func.__doc__
    docstring: Docstring = parse(func.__doc__)

    # Convert function signature and docs into annotations
    docstring_infos = create_typer_function_info(func, docstring)

    # Recreate function preserving any explicit annotations
    output_func = copy.copy(func)
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
                # annotations found but none for typer
                updated_annotation.__metadata__ += (info,)
        else:
            # create annotation
            updated_annotation = typing.Annotated[updated_annotation, info]
        output_annotations[arg_name] = updated_annotation

    if "return" in output_annotations:
        output_annotations["return"] = func.__annotations__["return"]

    output_func.__annotations__ = output_annotations
    output_func.__doc__ = docstring.description
    return output_func
