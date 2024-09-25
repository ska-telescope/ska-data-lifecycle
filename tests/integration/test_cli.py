"""Cli test module."""

import pytest
from typer.testing import CliRunner

from ska_dlm.cli import app

runner = CliRunner()


@pytest.mark.integration_test
def test_cli_help():
    """Test CLI help loads."""
    runner.invoke(app, ["--help"])
