"""DLM package for ska-data-lifecycle."""

import logging
import os

import benedict
import ska_ser_logging
import yaml

# from . import dlm_db, dlm_ingest, dlm_migration, dlm_request, dlm_storage
from . import dlm_db

__author__ = """Andreas Wicenec"""
__email__ = "andreas.wicenec@icrar.org"
__version__ = "0.0.1"

DLM_PATH = os.path.dirname(__file__)

ska_ser_logging.configure_logging()
logger = logging.getLogger(__name__)


def read_config(cfg_file: str = f"{DLM_PATH}/config.yaml") -> dict:
    """Read the config file and return the config dictionary."""
    with open(cfg_file, "r", encoding="utf-8") as file:
        cfg = benedict.benedict(yaml.safe_load(file))

    # TODO: Check validity and defaults.
    # cfg.REST.cfg_file = cfg.REST.cfg_file.format(**locals())
    if cfg.DB.password.startswith("!"):
        try:
            with open(f"{DLM_PATH}/../../.secrets.yaml", "r", encoding="utf-8") as file:
                secrets = benedict.benedict(yaml.safe_load(file))
            if cfg.DB.password[1:] in secrets:
                cfg.DB.password = secrets[cfg.DB.password[1:]]
        except FileNotFoundError:
            logger.error("secrets file not found!")
    return cfg


CONFIG = read_config()
CONFIG.REST.cfg_file = CONFIG.REST.cfg_file.format(**locals())

__all__ = [
    "DLM_PATH",
    "CONFIG",
    "dlm_db",
]
