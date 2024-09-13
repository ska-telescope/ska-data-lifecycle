"""Common utilities for CLI modules."""

import copy
import inspect
import types
import typing
from datetime import timedelta
from types import NoneType
from typing import Callable, ParamSpec, TypeVar, get_args

import fastapi
import fastapi.params
import typer
from docstring_parser import Docstring, DocstringStyle, compose, parse
from pydantic.fields import FieldInfo
from rich import print as rich_print

ParamsT = ParamSpec("ParamsT")
ReturnT = TypeVar("ReturnT")


def _iterate_exception_causes(ex: Exception):
    while ex:
        yield ex
        ex = ex.__cause__


def dump_short_stacktrace(ex: Exception):
    """Register custom stacktrace print for DBQueryError."""
    full_msg = ", caused by: ".join(f"{ex}" for ex in _iterate_exception_causes(ex))
    rich_print(f"[bold red]ERROR![/bold red]: {full_msg}")
    return 1


def add_as_typer_command(
    app: typer.Typer,
    func: Callable[ParamsT, ReturnT],
):
    """Add a typer command for the given callable function.

    The result of invoking the function is printed onto the screen. Certain exceptions are
    summarised in a single line instead of resulting on a full stack trace. Users can add/remove
    exceptions from getting this special treatment.

    Parameters
    ----------
    app : typer.Typer
        _description_
    func : Callable[ParamsT, ReturnT]
        _description_
    """
    app.command()(typer_docstring(func))


def fastapi_auto_annotate(app: fastapi.FastAPI):
    """Automatically applies `fastapi_docstring_annotate` to all FastAPI app routes."""

    def api_route(
        self,  # pylint: disable=unused-argument
        path: str,
        *_,
        **kwargs,
    ):
        def decorator(func):
            app.router.add_api_route(path, fastapi_docstring_annotate(func), **kwargs)
            return func

        return decorator

    app.router.api_route = types.MethodType(api_route, app)
    return app


def create_fastapi_field(
    param_type: type,
    **param_kwargs,
) -> FieldInfo:
    """Create a FastAPI field from kwargs."""
    match param_type:
        case fastapi.params.Query:
            return fastapi.Query(**param_kwargs)
        case fastapi.params.Body:
            return fastapi.Body(**param_kwargs)
        case _:
            raise NotImplementedError()


def fastapi_docstring_annotate(
    func: typing.Callable[ParamsT, ReturnT]
) -> typing.Callable[ParamsT, ReturnT]:
    """Decorator that generates FastAPI annotations from the function signature and docstring.

    Parameters
    ----------
    func : typing.Callable[ParamsT, T]
        _description_

    Returns
    -------
    typing.Callable[ParamsT, T]
        _description_
    """
    output_func = copy.copy(func)

    # Collect information about the parameters of the function
    parameters: dict[str, dict] = {}
    kinds: dict[str, type] = {}

    # Parse signature first so all parameter names are populated
    signature = inspect.signature(func)
    for arg_name, param in signature.parameters.items():
        parameters[arg_name] = {}
        kinds[arg_name] = (
            fastapi.params.Query
            if set(get_args(param.annotation)).issubset((str, timedelta, float, int, NoneType))
            else fastapi.params.Body
        )

    # Parse docstring
    assert func.__doc__
    docstring: Docstring = parse(func.__doc__)

    # extract as help messages from docstring (if present)
    for par in docstring.params:
        if par.arg_name in parameters:
            parameters[par.arg_name]["description"] = par.description
            # print(par.is_optional)

    # Transform the parameters into info instances
    docstring_infos: dict[str, FieldInfo] = {
        arg_name: create_fastapi_field(kinds[arg_name], **param_kwargs)
        for arg_name, param_kwargs in parameters.items()
    }

    output_annotations: dict = {}
    for arg_name, info in docstring_infos.items():
        updated_annotation: type | typing.Annotated = copy.deepcopy(func.__annotations__[arg_name])
        if hasattr(updated_annotation, "__metadata__"):
            updated = False
            for meta in updated_annotation.__metadata__:
                if isinstance(meta, FieldInfo):
                    # override missing help with docstring
                    if meta.description is None:
                        meta.description = copy.deepcopy(info.description)

                    updated = True
            if not updated:
                # annotations found but not for typer
                updated_annotation.__metadata__ += (info,)
        else:
            # create annotation
            updated_annotation = typing.Annotated[updated_annotation, info]
        output_annotations[arg_name] = updated_annotation

    if "return" in output_annotations:
        output_annotations["return"] = func.__annotations__["return"]

    output_func.__annotations__ = output_annotations
    docstring.blank_after_short_description = docstring.long_description is not None
    docstring.blank_after_long_description = docstring.long_description is not None
    # insert form feed \f to end FastAPI description
    docstring.long_description = f"{docstring.long_description or ''}\f"
    docstring.style = DocstringStyle.NUMPYDOC
    output_func.__doc__ = compose(docstring)
    return output_func


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
    output_func = copy.copy(func)

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

    # Transform the parameters into info instances
    docstring_infos: dict[str, typer.models.ParameterInfo] = {
        arg_name: create_typer_parameter(kinds[arg_name], **param_kwargs)
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
            updated_annotation = typing.Annotated[updated_annotation, info]
        output_annotations[arg_name] = updated_annotation

    if "return" in output_annotations:
        output_annotations["return"] = func.__annotations__["return"]

    output_func.__annotations__ = output_annotations
    output_func.__doc__ = docstring.description
    return output_func
