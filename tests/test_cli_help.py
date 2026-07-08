import importlib

from typer.testing import CliRunner

from ska_dlm.cli import app


def test_cli_help_renders() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"], prog_name="ska-dlm")

    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_cli_entrypoint_delegates_to_cli_main(monkeypatch) -> None:
    called = {}

    def fake_cli_main() -> None:
        called["called"] = True

    import ska_dlm.cli as cli_module
    import ska_dlm.cli_entrypoint as cli_entrypoint

    monkeypatch.setattr(cli_module, "main", fake_cli_main)
    cli_entrypoint.main()

    assert called["called"] is True
