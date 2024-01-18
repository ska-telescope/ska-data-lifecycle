"""DLM package for ska-data-lifecycle."""
import benedict
import os
import yaml
from ska_dlm import dlm_db, dlm_ingest, dlm_migration, dlm_request, dlm_storage

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"

DLM_PATH = os.path.dirname(__file__)


def read_config(cfg_file: str = f"{DLM_PATH}/config.yaml") -> dict:
    """
    Read the config file and return the config dictionary
    """
    with open(cfg_file, "r") as file:
        CONFIG = benedict.benedict(yaml.safe_load(file))

    # TODO: Check validity and defaults.
    # CONFIG.REST.cfg_file = CONFIG.REST.cfg_file.format(**locals())
    if CONFIG.DB.password.startswith("!"):
        try:
            with open(f"{DLM_PATH}/../../.secrets.yaml", "r") as file:
                secrets = benedict.benedict(yaml.safe_load(file))
            if secrets.__contains__(CONFIG.DB.password[1:]):
                CONFIG.DB.password = secrets[CONFIG.DB.password[1:]]
        except FileNotFoundError:
            print("secrets file not found!")
    return CONFIG


CONFIG = read_config()
CONFIG.REST.cfg_file = CONFIG.REST.cfg_file.format(**locals())

__all__ = [
    "dlm_db",
    "dlm_ingest",
    "dlm_migration",
    "dlm_request",
    "dlm_storage",
    "CONFIG",
    "DLM_PATH",
]
