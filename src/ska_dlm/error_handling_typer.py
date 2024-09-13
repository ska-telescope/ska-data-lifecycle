import sys
from typing import Any, Callable, Type

import typer

ErrorHandlingCallback = Callable[[Exception], int]


class ErrorHandlingTyper(typer.Typer):
    """Derived Typer class with support for custom exception handling.

    Exceptions are handled when commands are invoked to preserve the annotations
    of the original command stored in the app instance.
    """

    error_handlers: dict[Any, ErrorHandlingCallback] = {}

    def error_handler(self, exc: Type[Exception]):
        """Extend the app with an custom exception handler."""

        def decorator(f: Callable[[Exception], int]):
            self.error_handlers[exc] = f
            return f

        return decorator

    def __call__(self, *args, **kwargs):
        try:
            super(ErrorHandlingTyper, self).__call__(*args, **kwargs)
        except Exception as e:
            try:
                if type(e) in self.error_handlers:
                    callback = self.error_handlers[type(e)]
                    exit_code = callback(e)
                    raise typer.Exit(code=exit_code)
                else:
                    # Raise to typer default exception handler
                    raise
            except typer.Exit as e:
                sys.exit(e.exit_code)
