"""Cli utilities test module."""

from typing import Annotated, Any

import typer
from docstring_parser import parse
from typer.models import ArgumentInfo, OptionInfo

from ska_dlm.cli_utils import typer_docstring


def mock_command(  # pylint: disable=unused-argument, too-many-arguments
    arg1: str,
    arg2: Annotated[str, typer.Argument(help="custom arg2 description")],
    arg3: Annotated[str, "some other annotation"],
    arg4: Annotated[str, typer.Argument()] = "default",
    opt1: str = "",
    opt2: str | None = None,
    opt3: Annotated[str, typer.Option(help="custom opt3 description")] = "abcd",
    opt4: Annotated[Any | None, typer.Option()] = None,
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
    opt1 : dict | list
        opt1 description
    opt2 : dict | list
        opt2 description
    opt3 : dict | list
        opt3 description
    opt4 : dict | list
        opt4 description
    """


def test_typerdoc_generator():
    """Test typer doc generator."""
    typed = typer_docstring(mock_command)
    docstring = parse(typed.__doc__)
    assert docstring.short_description == "Short description."
    assert docstring.long_description == "Long description across\nmultiple lines."

    ann = typed.__annotations__
    assert_parameter_info(ann["arg1"].__metadata__[0], ArgumentInfo, "arg1 description")
    assert_parameter_info(ann["arg2"].__metadata__[0], ArgumentInfo, "custom arg2 description")
    assert_parameter_info(ann["arg3"].__metadata__[1], ArgumentInfo, "arg3 description")
    assert_parameter_info(ann["arg4"].__metadata__[0], ArgumentInfo, "arg4 description")

    assert_parameter_info(ann["opt1"].__metadata__[0], OptionInfo, "opt1 description")
    assert_parameter_info(ann["opt2"].__metadata__[0], OptionInfo, "opt2 description")
    assert_parameter_info(ann["opt3"].__metadata__[0], OptionInfo, "custom opt3 description")
    assert_parameter_info(ann["opt4"].__metadata__[0], OptionInfo, "opt4 description")


def assert_parameter_info(
    parameter_info: typer.models.ParameterInfo, info_type: type, helpdoc: str
):
    """Assert ParameterInfo members match arguments."""
    assert isinstance(parameter_info, info_type)
    assert parameter_info.help == helpdoc
    assert parameter_info.default == ...
