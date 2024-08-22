"""Common utilities for interacting with Kubernetes"""

import logging
import os

from kubernetes import client, config, stream
from overrides import override

import tests.integration.client.dlm_ingest_client as dlm_ingest_requests
import tests.integration.client.dlm_migration_client as dlm_migration_requests
import tests.integration.client.dlm_request_client as dlm_request_requests
import tests.integration.client.dlm_storage_client as dlm_storage_requests
from tests.test_env import DlmTestClient

logger = logging.getLogger(__name__)

NAMESPACE = os.getenv("KUBE_NAMESPACE")
RCLONE_DEPLOYMENT = "ska-dlm-rclone"


class DlmTestClientK8s(DlmTestClient):
    """kubernetes test environment utilities."""

    def __init__(self):
        config.load_kube_config()
        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()

    @property
    def storage_requests(self):
        return dlm_storage_requests

    @property
    def request_requests(self):
        return dlm_request_requests

    @property
    def ingest_requests(self):
        return dlm_ingest_requests

    @property
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
            command=["/bin/sh", "-c", f"echo -n '{content}' > {rclone_path}"],
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
            command=["/bin/cat", f"]{rclone_path}"],
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
    def get_service_urls(self) -> dict:
        """Returns named map of the client URLs for each of the DLM services"""
        return {
            "dlm_gateway": f"http://ska-dlm-gateway.{NAMESPACE}.svc.cluster.local",
            "dlm_ingest": f"http://ska-dlm-gateway.{NAMESPACE}.svc.cluster.local",
            "dlm_request": f"http://ska-dlm-gateway.{NAMESPACE}.svc.cluster.local",
            "dlm_storage": f"http://ska-dlm-gateway.{NAMESPACE}.svc.cluster.local",
        }
