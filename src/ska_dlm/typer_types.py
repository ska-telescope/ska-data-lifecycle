"""Typer type annotations modules."""

import json
from typing import Annotated, Any, Optional

import typer


def json_object_or_array(value: str) -> dict | list:
    """Parse shell string to JSON object or array."""
    value = json.loads(value)
    if not isinstance(value, dict) and not isinstance(value, list):
        raise ValueError("invalid JSON dictionary or array")
    return value


def json_object(value: str) -> dict:
    """Parse shell string to JSON object."""
    value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("invalid JSON dictionary")
    return value


def json_array(value: str) -> list:
    """Parse shell string to JSON array."""
    value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError("invalid JSON array")
    return value


JsonObjectArg = Annotated[dict, typer.Argument(parser=json_object)]
"""dict literal type alias for typer."""

JsonObjectOption = Annotated[Optional[dict], typer.Option(parser=json_object)]
"""Optional[dict] literal type alias for typer."""

JsonArrayArg = Annotated[list, typer.Argument(parser=json_array)]
"""list literal type alias for typer."""

JsonArrayOption = Annotated[Optional[list], typer.Option(parser=json_array)]
"""Optional[list] literal type alias for typer."""

JsonContainerArg = Annotated[Any, typer.Argument(parser=json_object_or_array)]
"""dict | list literal type alias for typer.

NOTE: typer does not support union annotations.
"""

JsonContainerOption = Annotated[Optional[Any], typer.Option(parser=json_object_or_array)]
"""Optional[dict | list] literal type alias for typer.

NOTE: typer does not support union annotations.
"""
