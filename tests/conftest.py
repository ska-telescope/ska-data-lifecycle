"""Global test setup/teardown."""

import logging

import pytest

from ska_dlm import CONFIG
from tests.common_docker import DlmTestClientDocker
from tests.common_k8s import DlmTestClientK8s
from tests.common_local import DlmTestClientLocal
from tests.test_env import DlmTestClient


def pytest_addoption(parser):
    """Set up command line options."""
    parser.addoption("--env", action="store", default="local", help="local, docker, or k8s")
    parser.addoption("--auth", action="store", default="1", help="Use OAuth flow")


@pytest.fixture(name="env", scope="session")
def env_fixture(request: pytest.FixtureRequest) -> DlmTestClient:
    """Fixture that creates deployment environment specific client.

    Additionally overrides ska_dlm.CONFIG with the environment in the test runner runtime.

    Parameters
    ----------
    request
        pytest fixture request context.

    Returns
    -------
    DlmTestClient
        client interface to a test DLM deployment.

    Raises
    ------
    ValueError
        Invalid `--env` option provided to pytest
    """
    match request.config.getoption("--env"):
        case "local":
            env = DlmTestClientLocal()
        case "docker":
            env = DlmTestClientDocker()
        case "k8s":
            env = DlmTestClientK8s()


        case _:
            raise ValueError("unknown test env configuration")

    logging.info("using test config: %s", CONFIG)
    return env
