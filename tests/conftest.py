"""Global test setup/teardown."""

import os

import pytest

from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB


def pytest_addoption(parser):
    """Setup command line"""
    parser.addoption("--env", action="store", default="k8", help="k8 or docker")


@pytest.fixture(name="k8s setup", scope="session", autouse=True)
def configure(request):
    """Setup tests to run against instance running in Minikube."""  # noqa: D401

    # Run as "pythest --env k8" for Kube testing
    # Run as "pythest --env docker" for Docker testing
    # Run as "pythest --env local" for local testing
    env = request.config.getoption("--env")
    if env == "k8":
        CONFIG.REST.base_url = _generate_k8s_url("postgrest", "ska-dlm-postgrest")
        CONFIG.RCLONE.url = _generate_k8s_url("rclone", "ska-dlm-rclone")

        # Horrible hacks that are necessary due to static instances
        # pylint: disable-next=protected-access
        DB._api_url = CONFIG.REST.base_url
        CONFIG.TEST_ENV.env = "k8"

    elif env == "docker":
        CONFIG.REST.base_url = "http://dlm_postgrest:3000"
        CONFIG.RCLONE.url = "http://dlm_rclone:5572"
        DB._api_url = CONFIG.REST.base_url
        CONFIG.TEST_ENV.env = "docker"

    elif env == "local":
        CONFIG.REST.base_url = "http://localhost:3000"
        CONFIG.RCLONE.url = "http://localhost:5572"
        DB._api_url = CONFIG.REST.base_url
        CONFIG.TEST_ENV.env = "local"

    else:
        raise ValueError("Unknown test configuration")


def _generate_k8s_url(ingress_path: str, service_name: str):
    """
    Generate a URL appropriate to query depending on whether we are
    running with ingress or not.
    """

    namespace = os.getenv("KUBE_NAMESPACE")
    assert namespace

    if ingress := os.getenv("TEST_INGRESS"):
        return f"{ingress}/{namespace}/{ingress_path}"

    return f"http://{service_name}.{namespace}"
