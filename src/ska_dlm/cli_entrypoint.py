"""Console-script entrypoint for the ska-dlm CLI."""

from ska_dlm import cli as cli_module


def main() -> None:
    """Run the CLI application."""
    cli_module.main()
