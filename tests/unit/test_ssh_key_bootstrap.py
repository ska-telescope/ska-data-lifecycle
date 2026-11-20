"""Tests for the idempotent SSH key-pair bootstrap script."""

import os
import stat
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "ensure-rclone-ssh-key.sh"


def _run_bootstrap(key_dir: Path, fake_bin: Path) -> subprocess.CompletedProcess:
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "SSH_KEYGEN_CALLS": str(fake_bin / "calls"),
    }
    return subprocess.run(
        ["sh", str(SCRIPT), str(key_dir)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _fake_ssh_keygen(fake_bin: Path) -> None:
    fake_bin.mkdir()
    executable = fake_bin / "ssh-keygen"
    executable.write_text(
        "#!/bin/sh\n"
        "echo called >> \"$SSH_KEYGEN_CALLS\"\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = \"-f\" ]; then shift; key_file=$1; fi\n"
        "  shift\n"
        "done\n"
        "printf private > \"$key_file\"\n"
        "printf public > \"$key_file.pub\"\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def test_bootstrap_generates_a_missing_pair(tmp_path):
    fake_bin = tmp_path / "bin"
    _fake_ssh_keygen(fake_bin)
    key_dir = tmp_path / "keys"

    result = _run_bootstrap(key_dir, fake_bin)

    assert result.returncode == 0
    assert (key_dir / "id_rsa").read_text(encoding="utf-8") == "private"
    assert (key_dir / "id_rsa.pub").read_text(encoding="utf-8") == "public"
    assert stat.S_IMODE((key_dir / "id_rsa").stat().st_mode) == 0o600
    assert stat.S_IMODE((key_dir / "id_rsa.pub").stat().st_mode) == 0o644
    assert (fake_bin / "calls").read_text(encoding="utf-8") == "called\n"


def test_bootstrap_leaves_an_existing_pair_unchanged(tmp_path):
    fake_bin = tmp_path / "bin"
    _fake_ssh_keygen(fake_bin)
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    (key_dir / "id_rsa").write_text("existing-private", encoding="utf-8")
    (key_dir / "id_rsa.pub").write_text("existing-public", encoding="utf-8")

    result = _run_bootstrap(key_dir, fake_bin)

    assert result.returncode == 0
    assert (key_dir / "id_rsa").read_text(encoding="utf-8") == "existing-private"
    assert (key_dir / "id_rsa.pub").read_text(encoding="utf-8") == "existing-public"
    assert not (fake_bin / "calls").exists()


def test_bootstrap_fails_on_an_incomplete_pair_without_overwriting(tmp_path):
    fake_bin = tmp_path / "bin"
    _fake_ssh_keygen(fake_bin)
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    (key_dir / "id_rsa").write_text("partial-private", encoding="utf-8")

    result = _run_bootstrap(key_dir, fake_bin)

    assert result.returncode != 0
    assert "Incomplete SSH key pair" in result.stderr
    assert (key_dir / "id_rsa").read_text(encoding="utf-8") == "partial-private"
    assert not (fake_bin / "calls").exists()
