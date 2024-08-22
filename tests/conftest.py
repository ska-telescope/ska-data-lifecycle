"""Global test setup/teardown."""

import logging
import os

import pytest

from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB
from tests.common_docker import DlmTestClientDocker
from tests.common_k8s import DlmTestClientK8s
from tests.common_local import DlmTestClientLocal


def pytest_addoption(parser):
    """Setup command line"""
    parser.addoption("--env", action="store", default="local", help="local, docker, or k8s")
    parser.addoption("--auth", action="store", default="1", help="Use OAuth flow")


@pytest.fixture(name="env", scope="session")
def env_fixture(request):
    """Test client dependent utilties."""
    match request.config.getoption("--env"):
        case "local":
            env = DlmTestClientLocal()
        case "docker":
            env = DlmTestClientDocker()
        case "k8s":
            CONFIG.REST.base_url = _generate_k8s_url(
                ingress_path="postgrest", service_name="ska-dlm-postgrest"
            )
            # assert False, CONFIG.REST.base_url
            CONFIG.RCLONE.url = _generate_k8s_url(
                ingress_path="rclone", service_name="ska-dlm-rclone"
            )

            # Horrible hacks that are necessary due to static instances
            # pylint: disable-next=protected-access
            DB._api_url = CONFIG.REST.base_url
            env = DlmTestClientK8s()
        case _:
            raise ValueError("unknown test env configuration")

    logging.info("using test config: %s", CONFIG)
    return env


def _generate_k8s_url(ingress_path: str, service_name: str):
    """
    Generate a URL appropriate to query depending on whether
    ingress is running or not.
    """

    namespace = os.getenv("KUBE_NAMESPACE")
    assert namespace

    if host := os.getenv("TEST_INGRESS"):
        return f"http://{host}/{namespace}/{ingress_path}"

    # k8s service
    return f"http://{service_name}.{namespace}.svc.cluster.local"
