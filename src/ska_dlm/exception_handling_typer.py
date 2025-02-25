"""Error handler typer module."""

import sys
from collections.abc import Callable
from typing import Any

import typer
from overrides import override
from typer.core import TyperCommand
from typer.models import CommandFunctionType, CommandInfo, Default

from ska_dlm.typer_utils import typer_docstring

ErrorHandlingCallback = Callable[[Exception], int]


class ExceptionHandlingTyper(typer.Typer):
    """Derived Typer class with support for custom exception handling.

    Exceptions are handled when commands are invoked to preserve the annotations
    of the original command stored in the app instance.
    """

    exception_handlers: dict[Any, ErrorHandlingCallback] = {}

    def exception_handler(self, exc: type[Exception]):
        """Extend the app with an custom exception handler."""

        def decorator(f: Callable[[Exception], int]):
            self.exception_handlers[exc] = f
            return f

        return decorator

    @override
    def command(  # pylint: disable=too-many-arguments
        self,
        name: str | None = None,
        *,
        cls: type[TyperCommand] | None = None,
        context_settings: dict[Any, Any] | None = None,
        help: str | None = None,  # pylint: disable=redefined-builtin
        epilog: str | None = None,
        short_help: str | None = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        rich_help_panel: str | None = Default(None),
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        """Registers typer command with generated docstring."""
        if cls is None:
            cls = TyperCommand

        def decorator(f: CommandFunctionType) -> CommandFunctionType:
            self.registered_commands.append(
                CommandInfo(
                    name=name,
                    cls=cls,
                    context_settings=context_settings,
                    callback=typer_docstring(f),
                    help=help,
                    epilog=epilog,
                    short_help=short_help,
                    options_metavar=options_metavar,
                    add_help_option=add_help_option,
                    no_args_is_help=no_args_is_help,
                    hidden=hidden,
                    deprecated=deprecated,
                    # Rich settings
                    rich_help_panel=rich_help_panel,
                )
            )
            return f

        return decorator

    @override
    def __call__(self, *args, **kwargs):
        """Call the registered typer function."""
        try:
            super().__call__(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-exception-caught
            try:
                if type(e) in self.exception_handlers:
                    callback = self.exception_handlers[type(e)]
                    exit_code = callback(e)
                    raise typer.Exit(code=exit_code)
                # Raise to typer default exception handler
                raise
            except typer.Exit as exit_exc:
                sys.exit(exit_exc.exit_code)
