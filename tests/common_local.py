"""Common utilities for interacting with native system"""

import logging
import os
import tarfile

import docker

logger = logging.getLogger(__name__)

RCLONE_DEPLOYMENT = "dlm_rclone"


client = docker.from_env()


def _copy_to(src: str, dst: str):
    """Copy file to container"""
    name, dst = dst.split(":")
    container = client.containers.get(name)
    with tarfile.open(f"{src}.tar", "w") as tar:
        tar.add(src, arcname=os.path.basename(src))

    with open(f"{src}.tar", "rb") as data:
        container.put_archive(os.path.dirname(dst), data.read())


def _copy_from(src: str, dest: str):
    """Copy file from container"""
    name, src = src.split(":")
    container = client.containers.get(name)
    with open(dest, "wb") as file:
        bits, _ = container.get_archive(src)
        for chunk in bits:
            file.write(chunk)


def write_rclone_file_content(rclone_path: str, content: str):
    """Write the given text to a file local to rclone container."""
    os.makedirs(f"/tmp/{os.path.dirname(rclone_path)}", exist_ok=True)
    with open(f"/tmp/{rclone_path}", "wt", encoding="ascii") as file:
        file.write(content)

    _copy_to(f"/tmp/{rclone_path}", f"{RCLONE_DEPLOYMENT}:{rclone_path}")


def get_rclone_local_file_content(rclone_path: str):
    """Get the text content of a file local to rclone container"""
    _copy_from(f"{RCLONE_DEPLOYMENT}:{rclone_path}", f"/tmp/{rclone_path}.tar")

    with tarfile.open(f"/tmp/{rclone_path}.tar") as file:
        file.extractall("/tmp", filter="data")

    with open(f"/tmp/{os.path.basename(rclone_path)}", "rt", encoding="ascii") as file:
        return file.read()


def clear_rclone_data(path: str):
    """Delete all rclone data."""
    container = client.containers.get(RCLONE_DEPLOYMENT)
    container.exec_run(["/bin/sh", "-c", f"rm -rf {path}/*"])


def get_service_urls():
    """Returns named map of the client URLs for each of the DLM services"""
    urls = {
        "dlm_gateway": "http://localhost:8000",
        "dlm_ingest": "http://localhost:8000",
        "dlm_request": "http://localhost:8000",
        "dlm_storage": "http://localhost:8000",
    }
    return urls
