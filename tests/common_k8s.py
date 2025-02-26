"""Common utilities for interacting with Kubernetes."""

import logging
import os

from kubernetes import client, config, stream
from overrides import override

import tests.integration.client.data_item_client as data_item_requests
import tests.integration.client.dlm_ingest_client as dlm_ingest_requests
import tests.integration.client.dlm_migration_client as dlm_migration_requests
import tests.integration.client.dlm_request_client as dlm_request_requests
import tests.integration.client.dlm_storage_client as dlm_storage_requests
from ska_dlm import CONFIG
from ska_dlm.dlm_db.db_access import DB
from tests.test_env import DlmTestClient

logger = logging.getLogger(__name__)

NAMESPACE = os.getenv("KUBE_NAMESPACE")
RCLONE_DEPLOYMENT = "ska-dlm-rclone"


class DlmTestClientK8s(DlmTestClient):
    """Kubernetes test environment utilities.

    Test client for a deployment where all services run from within k8s
    and tests running outside the cluster if K8S_HOST_URL is defined, otherwise
    tests running inside the cluster.
    """

    def __init__(self):
        config.load_kube_config()
        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()

        # Horrible hacks that are necessary due to static instances
        dlm_storage_requests.STORAGE_URL = _generate_k8s_url("dlm", "ska-dlm-gateway")
        dlm_ingest_requests.INGEST_URL = _generate_k8s_url("dlm", "ska-dlm-gateway")
        dlm_request_requests.REQUEST_URL = _generate_k8s_url("dlm", "ska-dlm-gateway")
        data_item_requests.REQUEST_URL = _generate_k8s_url("dlm", "ska-dlm-gateway")
        dlm_migration_requests.MIGRATION_URL = _generate_k8s_url("dlm", "ska-dlm-gateway")

        CONFIG.REST.base_url = _generate_k8s_url(
            ingress_path="postgrest", service_name="ska-dlm-postgrest"
        )
        CONFIG.RCLONE.url = _generate_k8s_url(ingress_path="rclone", service_name="ska-dlm-rclone")
        DB.api_url = CONFIG.REST.base_url

    @property
    @override
    def storage_requests(self):
        return dlm_storage_requests

    @property
    @override
    def request_requests(self):
        return dlm_request_requests

    @property
    @override
    def data_item_requests(self):
        return data_item_requests

    @property
    @override
    def ingest_requests(self):
        return dlm_ingest_requests

    @property
    @override
    def migration_requests(self):
        return dlm_migration_requests

    @override
    def write_rclone_file_content(self, rclone_path: str, content: str):
        """Write the given text to a file local to rclone."""
        pod_name = self._get_pod_name(RCLONE_DEPLOYMENT)
        stream.stream(
            self.core_api.connect_get_namespaced_pod_exec,
            pod_name,
            NAMESPACE,
            command=[
                "/bin/sh",
                "-c",
                f"echo -n '{content}' | install -D /dev/stdin {rclone_path}",
            ],
            stdout=True,
        )

    @override
    def get_rclone_local_file_content(self, rclone_path: str) -> str:
        """Get the text content of a file local to rclone"""
        pod_name = self._get_pod_name(RCLONE_DEPLOYMENT)
        content = stream.stream(
            self.core_api.connect_get_namespaced_pod_exec,
            pod_name,
            NAMESPACE,
            command=["/bin/cat", f"{rclone_path}"],
            stdout=True,
        )
        return content

    @override
    def clear_rclone_data(self, path: str):
        """Delete all local rclone data."""
        pod_name = self._get_pod_name(RCLONE_DEPLOYMENT)
        output = stream.stream(
            self.core_api.connect_get_namespaced_pod_exec,
            pod_name,
            NAMESPACE,
            command=["/bin/sh", "-c", f"rm -rf {path}/*"],
            stdout=True,
        )
        return output

    def create_rclone_directory(self, path: str):
        """Create rclone directory."""
        pod_name = self._get_pod_name(RCLONE_DEPLOYMENT)
        output = stream.stream(
            self.core_api.connect_get_namespaced_pod_exec,
            pod_name,
            NAMESPACE,
            command=["/bin/sh", "-c", f"mkdir -p {path}"],
            stdout=True,
        )
        return output

    def _get_pod_name(self, pod_name: str):
        deployment = self.apps_api.read_namespaced_deployment(pod_name, NAMESPACE)
        labels: dict = deployment.spec.selector.match_labels
        selector = ",".join(f"{k}={v}" for k, v in labels.items())
        pods = self.core_api.list_namespaced_pod(NAMESPACE, label_selector=selector)
        assert len(pods.items) == 1, (
            f"Before removing this assert, make sure {pod_name} "
            "is mounted to a volume that all pods can access"
        )

        pod_name = pods.items[0].metadata.name
        return pod_name

    @override
    def get_gateway_url(self) -> str:
        """Get the gateway url."""
        return _generate_k8s_url(ingress_path="dlm", service_name="ska-dlm-gateway")


def _generate_k8s_url(ingress_path: str, service_name: str):
    """Generate the service host URL.

    Uses the ingress path if K8S_HOST_URL envvar is defined.

    Parameters
    ----------
    ingress_path
        ingress path to append to the url host
    service_name
        service name for generating the url if ingress is not enabled
    """
    if host_url := os.getenv("K8S_HOST_URL"):
        # public host with ingress path
        return f"{host_url}/{NAMESPACE}/{ingress_path}"

    # k8s service
    return f"http://{service_name}.{NAMESPACE}"
