# pylint: disable=no-member
"""DLM package for ska-data-lifecycle."""
import os
import benedict
import yaml
from . import dlm_db

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"

DLM_PATH = os.path.dirname(__file__)


def read_config(cfg_file: str = f"{DLM_PATH}/config.yaml") -> dict:
    """
    Read the config file and return the config dictionary
    """
    with open(cfg_file, "r", encoding="utf-8") as file:
        CONFIG = benedict.benedict(yaml.safe_load(file))

    # TODO: Check validity and defaults.
    # CONFIG.REST.cfg_file = CONFIG.REST.cfg_file.format(**locals())
    if CONFIG.DB.password.startswith("!"):
        try:
            with open(f"{DLM_PATH}/../../.secrets.yaml", "r", encoding="utf-8") as file:
                secrets = benedict.benedict(yaml.safe_load(file))
            if CONFIG.DB.password[1:] in secrets:
                CONFIG.DB.password = secrets[CONFIG.DB.password[1:]]
        except FileNotFoundError:
            print("secrets file not found!")
    return CONFIG


CONFIG = read_config()
CONFIG.REST.cfg_file = CONFIG.REST.cfg_file.format(**locals())

__all__ = [
    "DLM_PATH",
    "CONFIG",
    "dlm_db",
]
