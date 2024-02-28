"""Common utilities for interacting with Kubernetes"""

import logging
import os

from kubernetes import client, config, stream

logger = logging.getLogger(__name__)

NAMESPACE = os.getenv("KUBE_NAMESPACE")
RCLONE_DEPLOYMENT = "ska-dlm-rclone"
RCLONE_HOME = "/data"

config.load_kube_config()
core_api = client.CoreV1Api()
apps_api = client.AppsV1Api()


def write_rclone_file_content(rclone_path: str, content: str):
    """Write the given text to a file local to rclone."""
    pod_name = _get_rclone_pod_name()
    stream.stream(
        core_api.connect_get_namespaced_pod_exec,
        pod_name,
        NAMESPACE,
        command=["/bin/sh", "-c", f"echo -n '{content}' > {RCLONE_HOME}/{rclone_path}"],
        stdout=True,
    )


def get_rclone_local_file_content(rclone_path: str):
    """Get the text content of a file local to rclone"""
    pod_name = _get_rclone_pod_name()
    content = stream.stream(
        core_api.connect_get_namespaced_pod_exec,
        pod_name,
        NAMESPACE,
        command=["/bin/cat", f"{RCLONE_HOME}/{rclone_path}"],
        stdout=True,
    )
    return content


def clear_rclone_data():
    """Delete all local rclone data."""
    pod_name = _get_rclone_pod_name()
    output = stream.stream(
        core_api.connect_get_namespaced_pod_exec,
        pod_name,
        NAMESPACE,
        command=["/bin/sh", "-c", f"rm -rf {RCLONE_HOME}/*"],
        stdout=True,
    )
    return output


def _get_rclone_pod_name():
    deployment = apps_api.read_namespaced_deployment(RCLONE_DEPLOYMENT, NAMESPACE)
    labels: dict = deployment.spec.selector.match_labels
    selector = ",".join(f"{k}={v}" for k, v in labels.items())
    pods = core_api.list_namespaced_pod(NAMESPACE, label_selector=selector)
    assert len(pods.items) == 1, (
        f"Before removing this assert, make sure {RCLONE_HOME} "
        "is mounted to a volume that all pods can access"
    )

    pod_name = pods.items[0].metadata.name
    return pod_name
