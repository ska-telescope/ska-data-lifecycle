"""DLM package for ska-data-lifecycle."""

import os

import yaml
from benedict import benedict

# from . import dlm_db, dlm_ingest, dlm_migration, dlm_request, dlm_storage
from . import dlm_db

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"

DLM_PATH = os.path.dirname(__file__)


def read_config(cfg_file: str = f"{DLM_PATH}/config.yaml") -> benedict:
    """Read the config file and return the config dictionary."""
    with open(cfg_file, "r", encoding="utf-8") as file:
        return benedict(yaml.safe_load(file))


CONFIG = read_config()

__all__ = [
    "DLM_PATH",
    "CONFIG",
    "dlm_db",
]
