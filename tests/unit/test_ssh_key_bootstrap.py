"""Tests for the idempotent SSH key-pair bootstrap script."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parents[1] / "ensure-rclone-ssh-key.sh"
CHART = Path(__file__).parents[2] / "charts" / "ska-dlm"


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
        'echo called >> "$SSH_KEYGEN_CALLS"\n'
        'while [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "-f" ]; then shift; key_file=$1; fi\n'
        "  shift\n"
        "done\n"
        'printf private > "$key_file"\n'
        'printf public > "$key_file.pub"\n',
        encoding="utf-8",
    )
    executable.chmod(0o755)


def test_bootstrap_generates_a_missing_pair(tmp_path):
    """Generate a private and public key when neither exists."""
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
    """Keep an existing pair without invoking ssh-keygen."""
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
    """Reject an incomplete pair without replacing the existing private key."""
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


@pytest.mark.parametrize("existing", ["missing", "complete", "incomplete", "api-error"])
def test_helm_bootstrap_secret_handling(tmp_path, existing):  # pylint: disable=too-many-locals
    """Run the rendered hook scripts against a fake API without exposing key material."""
    if not shutil.which("helm"):
        pytest.skip("helm is not installed")
    rendered = subprocess.run(
        [
            "helm",
            "template",
            "test",
            str(CHART),
            "--show-only",
            "templates/rclone-key-bootstrap.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    documents = list(yaml.safe_load_all(rendered.stdout))
    job = next(document for document in documents if document["kind"] == "Job")
    pod = job["spec"]["template"]["spec"]
    check, generate = pod["initContainers"]
    create = pod["containers"][0]
    assert check["image"] == create["image"] == "alpine/k8s:1.30.14"
    assert generate["image"] == "linuxserver/openssh-server:version-9.9_p2-r0"
    assert pod["volumes"] == [{"name": "keys", "emptyDir": {"medium": "Memory"}}]

    fake_bin = tmp_path / "bin"
    _fake_ssh_keygen(fake_bin)
    kubectl = fake_bin / "kubectl"
    kubectl.write_text(
        "#!/bin/sh\n"
        'if [ "$SECRET_STATE" = api-error ]; then echo "API unavailable" >&2; exit 1; fi\n'
        'if [ "$1" = create ]; then echo created >> "$KUBECTL_CALLS"; exit 0; fi\n'
        'case "$*" in\n'
        '  *--output=name*) [ "$SECRET_STATE" = missing ] || echo secret/name ;;\n'
        '  *id_rsa\\\\.pub*) [ "$SECRET_STATE" = complete ] && printf public ;;\n'
        "  *id_rsa*) printf private ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "SSH_KEYGEN_CALLS": str(fake_bin / "calls"),
        "KUBECTL_CALLS": str(fake_bin / "kubectl-calls"),
        "SECRET_STATE": existing,
        "SSH_KEY_SECRET_NAME": "test-key",
        "POD_NAMESPACE": "test",
    }

    results = []
    for container in (check, generate, create):
        script = container["args"][0].replace("/keys", str(key_dir))
        result = subprocess.run(
            ["sh", "-ec", script], capture_output=True, text=True, env=environment, check=False
        )
        results.append(result)
        if result.returncode:
            break

    assert all(
        "private" not in result.stdout and "public" not in result.stdout for result in results
    )
    if existing in {"incomplete", "api-error"}:
        assert results[-1].returncode != 0
        assert not (fake_bin / "calls").exists()
        assert not (fake_bin / "kubectl-calls").exists()
    else:
        assert len(results) == 3 and all(result.returncode == 0 for result in results)
        assert (fake_bin / "calls").exists() is (existing == "missing")
        assert (fake_bin / "kubectl-calls").exists() is (existing == "missing")
