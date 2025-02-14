"""Typer and FastAPI utilties test module."""

import types
from typing import Annotated, Any

import fastapi.params
import typer
from docstring_parser import parse
from pydantic_core import PydanticUndefined
from typer.models import ArgumentInfo, OptionInfo

from ska_dlm.fastapi_utils import fastapi_docstring_annotate, get_underlying_type
from ska_dlm.typer_utils import typer_docstring


def test_get_annotation_types():
    assert get_underlying_type(str) == (str,)
    assert get_underlying_type(str | None) == (str, types.NoneType)
    assert get_underlying_type(Annotated[str, "info"]) == (str,)
    assert get_underlying_type(Annotated[str | None, "info"]) == (str, types.NoneType)


def mock_command(  # pylint: disable=unused-argument, too-many-arguments
    arg1: str,
    arg2: Annotated[
        str,
        typer.Argument(help="typer arg2 description"),
        fastapi.Query(description="fastapi arg2 description"),
    ],
    arg3: Annotated[str, "some other annotation"],
    arg4: Annotated[str, typer.Argument()] = "default",
    opt1: str = "",
    opt2: str | None = None,
    opt3: Annotated[
        str,
        typer.Option(help="typer opt3 description"),
        fastapi.Query(description="fastapi opt3 description"),
    ] = "abcd",
    opt4: Annotated[Any | None, typer.Option()] = None,
    header1: Annotated[str | None, fastapi.Header()] = None,
    cookie1: Annotated[str | None, fastapi.Cookie()] = None,
    file1: Annotated[str | None, fastapi.File()] = None,
    dep1: Annotated[str | None, fastapi.Depends()] = None,
    sec1: Annotated[str | None, fastapi.Security()] = None,
):
    """
    Short description.

    Long description across
    multiple lines.

    Parameters
    ----------
    arg1 : str
        arg1 description
    arg2 : str
        arg2 description
    arg3 : str
        arg3 description
    arg4 : str
        arg4 description
    opt1 : str
        opt1 description
    opt2 : str | None
        opt2 description
    opt3 : str
        opt3 description
    opt4 : Any | None
        opt4 description
    cookie1 : str | None
        cookie1 description
    file1 : str | None
        file1 description
    """


def test_fastapi_docstring_generator():
    """Test FastAPI docstring generation."""
    typed = fastapi_docstring_annotate(mock_command)
    docstring = parse(typed.__doc__)
    assert docstring.short_description == "Short description."
    assert docstring.long_description == "Long description across\nmultiple lines."

    ann = typed.__annotations__
    assert_fastapi_annotation_doc(ann["arg1"], fastapi.params.Query, "arg1 description")
    assert_fastapi_annotation_doc(ann["arg2"], fastapi.params.Query, "fastapi arg2 description")
    assert_fastapi_annotation_doc(ann["arg3"], fastapi.params.Query, "arg3 description")
    assert_fastapi_annotation_doc(ann["arg4"], fastapi.params.Query, "arg4 description")

    assert_fastapi_annotation_doc(ann["opt1"], fastapi.params.Query, "opt1 description")
    assert_fastapi_annotation_doc(ann["opt2"], fastapi.params.Query, "opt2 description")
    assert_fastapi_annotation_doc(ann["opt3"], fastapi.params.Query, "fastapi opt3 description")
    assert_fastapi_annotation(ann["opt4"], types.NoneType)

    assert_fastapi_annotation_doc(ann["cookie1"], fastapi.params.Cookie, "cookie1 description")
    assert_fastapi_annotation_doc(ann["file1"], fastapi.params.File, "file1 description")
    assert_fastapi_annotation(ann["dep1"], fastapi.params.Depends)
    assert_fastapi_annotation(ann["sec1"], fastapi.params.Security)


def test_typer_docstring_generator():
    """Test typer doc generator."""
    typed = typer_docstring(mock_command)
    docstring = parse(typed.__doc__)
    assert docstring.short_description == "Short description."
    assert docstring.long_description == "Long description across\nmultiple lines."

    ann = typed.__annotations__
    assert_typer_annotation(ann["arg1"], ArgumentInfo, "arg1 description")
    assert_typer_annotation(ann["arg2"], ArgumentInfo, "typer arg2 description")
    assert_typer_annotation(ann["arg3"], ArgumentInfo, "arg3 description")
    assert_typer_annotation(ann["arg4"], ArgumentInfo, "arg4 description")

    assert_typer_annotation(ann["opt1"], OptionInfo, "opt1 description")
    assert_typer_annotation(ann["opt2"], OptionInfo, "opt2 description")
    assert_typer_annotation(ann["opt3"], OptionInfo, "typer opt3 description")
    assert_typer_annotation(ann["opt4"], OptionInfo, "opt4 description")


def assert_typer_annotation(annotation: Any, info_type: type, helpdoc: str):
    """Assert annotation countains specified typer info."""
    found = 0
    info = None
    for meta in annotation.__metadata__:
        if isinstance(meta, info_type):
            info = meta
            found += 1

    assert found == 1, f"expected a single {info_type} in {annotation.__metadata__}"
    assert isinstance(info, info_type)
    assert info.help == helpdoc
    assert info.default == ...


def assert_fastapi_annotation(annotation: Any, info_type: type):
    found = 0
    for meta in annotation.__metadata__:
        if isinstance(meta, info_type):
            found += 1
    assert found == 1, f"expected a single {info_type} in {annotation.__metadata__}"


def assert_fastapi_annotation_doc(annotation: Any, info_type: type, helpdoc: str):
    """Assert annotations contains specificed fastapi info."""
    found = 0
    info = None
    for meta in annotation.__metadata__:
        if isinstance(meta, info_type):
            info = meta
            found += 1

    assert found == 1, f"expected a single {info_type} in {annotation.__metadata__}"
    assert isinstance(info, info_type)
    assert info.description == helpdoc
    assert info.default == PydanticUndefined
