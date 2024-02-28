"""Global test setup/teardown."""

import os

import pytest

from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB


@pytest.fixture(name="k8s setup", scope="session", autouse=True)
def configure():
    """Setup tests to run against instance running in Minikube."""  # noqa: D401
    CONFIG.REST.base_url = _generate_k8s_url("postgrest", "ska-dlm-postgrest")
    CONFIG.RCLONE.url = _generate_k8s_url("rclone", "ska-dlm-rclone")

    # Horrible hacks that are necessary due to static instances
    # pylint: disable-next=protected-access
    DB._api_url = CONFIG.REST.base_url


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
