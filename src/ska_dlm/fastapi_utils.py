"""Common utilities for CLI modules."""

import copy
import inspect
import types
import typing
from datetime import timedelta
from types import NoneType, UnionType
from typing import ParamSpec, TypeVar, get_args

import fastapi
import fastapi.params
import jwt
from docstring_parser import Docstring, DocstringStyle, compose, parse
from pydantic.fields import FieldInfo
from typing_extensions import _AnnotatedAlias

ParamsT = ParamSpec("ParamsT")
ReturnT = TypeVar("ReturnT")


def get_underlying_type(annotation: type | UnionType | _AnnotatedAlias) -> tuple[type, ...]:
    """Get the underlying type union of an annotation."""
    while isinstance(annotation, _AnnotatedAlias):
        annotation = get_args(annotation)[0]
    return get_args(annotation) if isinstance(annotation, UnionType) else (annotation,)


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


def create_fastapi_info(
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


def create_fastapi_function_info(
    func: typing.Callable[ParamsT, ReturnT], doc: Docstring
) -> dict[str, FieldInfo]:
    """Create dictionary of default FastAPI annotations for a given function."""
    # Collect information about the parameters of the function
    kinds: dict[str, type] = {}
    parameters: dict[str, dict] = {}

    # Parse signature first so all parameter names are populated
    signature = inspect.signature(func)
    for arg_name, param in signature.parameters.items():
        parameters[arg_name] = {}
        kinds[arg_name] = (
            fastapi.params.Query
            if set(get_underlying_type(param.annotation)).issubset(
                {str, timedelta, float, int, NoneType}
            )
            else fastapi.params.Body
        )

    # extract as help messages from docstring (if present)
    for par in doc.params:
        if par.arg_name in parameters:
            parameters[par.arg_name]["description"] = par.description

    # Transform the parameters into info instances
    infos: dict[str, FieldInfo] = {
        arg_name: create_fastapi_info(kinds[arg_name], **param_kwargs)
        for arg_name, param_kwargs in parameters.items()
    }
    return infos


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
    # Parse docstring
    docstring: Docstring = parse(func.__doc__)

    # Convert function signature and docs into annotations
    docstring_infos = create_fastapi_function_info(func, docstring)

    # Recreate function preserving any explicit annotations
    output_func = copy.copy(func)
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
                # annotations found but none for fastapi
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


def decode_bearer(bearer: str) -> dict:
    """Extract token from Bearer string and decode."""
    if bearer:
        bearer_token = bearer.split(" ")[1]
        return jwt.decode(bearer_token, options={"verify_signature": False})
    return None
