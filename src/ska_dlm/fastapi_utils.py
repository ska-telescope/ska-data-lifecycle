"""Common utilities for CLI modules."""

import copy
import inspect
import types
import typing
from datetime import timedelta
from types import NoneType, UnionType
from typing import Any, ParamSpec, TypeVar, get_args

import fastapi
import fastapi.params
import jwt
from docstring_parser import Docstring, DocstringStyle, compose, parse
from pydantic.fields import FieldInfo
from typing_extensions import Annotated

ParamsT = ParamSpec("ParamsT")
ReturnT = TypeVar("ReturnT")
RoutableT = TypeVar("RoutableT", fastapi.FastAPI, fastapi.APIRouter)


def get_underlying_type(annotation: type | UnionType | Annotated) -> tuple[type, ...]:
    """Get the underlying type union of an annotation."""
    while isinstance(annotation, Annotated):
        annotation = get_args(annotation)[0]
    return get_args(annotation) if isinstance(annotation, UnionType) else (annotation,)


def fastapi_auto_annotate(app: RoutableT) -> RoutableT:
    """Automatically applies `fastapi_docstring_annotate` to all FastAPI app routes."""

    def api_route(self: fastapi.APIRouter, path: str, *_, **kwargs):
        def decorator(func):
            if kwargs["operation_id"] is None:
                kwargs["operation_id"] = func.__qualname__
            self.add_api_route(path, fastapi_docstring_annotate(func), **kwargs)
            return func

        return decorator

    if isinstance(app, fastapi.FastAPI):
        app.router.api_route = types.MethodType(api_route, app.router)
    elif isinstance(app, fastapi.APIRouter):
        app.api_route = types.MethodType(api_route, app)
    return app


def create_fastapi_parameter_info(param_type: type, *param_args, **param_kwargs) -> Any:
    """Create a FastAPI field info."""
    match param_type:
        case fastapi.params.Query:
            result = fastapi.Query(*param_args, **param_kwargs)
        case fastapi.params.Body:
            result = fastapi.Body(*param_args, **param_kwargs)
        case fastapi.params.Cookie:
            result = fastapi.Cookie(*param_args, **param_kwargs)
        case fastapi.params.Header:
            result = fastapi.Header(*param_args, **param_kwargs)
        case fastapi.params.File:
            result = fastapi.File(*param_args, **param_kwargs)
        case fastapi.params.Depends:
            result = fastapi.Depends(*param_args, **param_kwargs)
        case fastapi.params.Security:
            result = fastapi.Security(*param_args, **param_kwargs)
        case fastapi.params._Unset:  # pylint: disable=protected-access
            result = None
        case _:
            raise NotImplementedError(param_type)
    return result


def create_fastapi_function_info(
    func: typing.Callable[ParamsT, ReturnT], doc: Docstring
) -> dict[str, Any]:
    """Create dictionary of default FastAPI annotations for a given function."""
    # Collect information about the parameters of the function
    kinds: dict[str, type] = {}
    parameters: dict[str, tuple[list, dict]] = {}

    # Parse signature first so all parameter names are populated
    signature = inspect.signature(func)
    for arg_name, param in signature.parameters.items():
        parameters[arg_name] = ([], {})
        if set(get_underlying_type(param.annotation)).issubset(
            {bool, str, timedelta, float, int, NoneType}
        ):
            kinds[arg_name] = fastapi.params.Query
        elif set(get_underlying_type(param.annotation)).issubset({dict, list, NoneType}):
            kinds[arg_name] = fastapi.params.Body
        else:
            kinds[arg_name] = fastapi.params._Unset  # pylint: disable=protected-access

    # extract as help messages from docstring (if present)
    for par in doc.params:
        if par.arg_name in parameters and not isinstance(
            kinds[par.arg_name], fastapi.params.Depends
        ):
            parameters[par.arg_name][1]["description"] = par.description

    # Transform the parameters into info instances
    infos: dict[str, Any] = {
        arg_name: create_fastapi_parameter_info(kinds[arg_name], *params[0], **params[1])
        for arg_name, params in parameters.items()
    }
    return infos


def fastapi_docstring_annotate(
    func: typing.Callable[ParamsT, ReturnT],
) -> typing.Callable[ParamsT, ReturnT]:
    """Decorate FastAPI function with doc annotations from the signature and docstring.

    FastAPI functions require parameter docstrings inside FastAPI parameter annotations instead
    of the __doc__ member otherwise requiring docstring duplication to share parameter docstrings
    between sphinx, fastapi and typer.

    The __doc__ member is also stripped to only short and long description.

    Parameters
    ----------
    func
        A fastapi endpoint function to modify the docstring and annotation.

    Returns
    -------
    typing.Callable[ParamsT, ReturnT]
        Resulting fastapi endpoint with modified docstring and annotations.
    """
    # Parse docstring
    docstring: Docstring = parse(func.__doc__ or "")

    # Convert function signature and docs into annotations
    generated_infos = create_fastapi_function_info(func, docstring)

    # Recreate function preserving any explicit annotations
    output_func = copy.copy(func)
    output_annotations: dict = {}
    for arg_name, arg_info in generated_infos.items():
        updated_annotation: type | typing.Annotated = copy.deepcopy(func.__annotations__[arg_name])
        if hasattr(updated_annotation, "__metadata__"):
            updated = False
            for meta in updated_annotation.__metadata__:
                if isinstance(meta, FieldInfo):
                    # override missing help with docstring
                    if meta.description is None:
                        meta.description = copy.deepcopy(arg_info.description)

                    updated = True
            if not updated:
                # annotations found but none for fastapi
                updated_annotation.__metadata__ += (arg_info,)
        else:
            # create annotation
            updated_annotation = typing.Annotated[updated_annotation, arg_info]
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


def decode_bearer(bearer: str | None) -> dict | None:
    """Extract token from Bearer string and decode."""
    if bearer:
        bearer_token = bearer.split(" ")[1]
        return jwt.decode(bearer_token, options={"verify_signature": False})
    return None
