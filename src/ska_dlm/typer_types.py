"""Typer type annotations modules."""

import json
from typing import Annotated, Any

import typer

__all__ = [
    "JsonObjectArg",
    "JsonObjectOption",
    "JsonArrayArg",
    "JsonArrayOption",
    "JsonContainerArg",
    "JsonContainerOption",
]


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


JsonObjectArg = Annotated[dict, typer.Argument(parser=json_object, help="JSON object")]
"""dict literal type alias for typer."""

JsonObjectOption = Annotated[dict | None, typer.Option(parser=json_object, help="JSON object")]
"""dict | None literal type alias for typer."""

JsonArrayArg = Annotated[list, typer.Argument(parser=json_array, help="JSON array")]
"""list literal type alias for typer."""

JsonArrayOption = Annotated[list | None, typer.Option(parser=json_array, help="JSON array")]
"""list | None literal type alias for typer."""

JsonContainerArg = Annotated[
    Any, typer.Argument(parser=json_object_or_array, help="JSON object or array")
]
"""dict | list literal type alias for typer.

NOTE: typer does not support union annotations.
"""

JsonContainerOption = Annotated[
    Any | None, typer.Option(parser=json_object_or_array, help="JSON object or array")
]
"""dict | list | None literal type alias for typer.

NOTE: typer does not support union annotations.
"""
