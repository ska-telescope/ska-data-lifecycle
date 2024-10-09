"""
SKA Data Lifecycle Management (DLM) package.

To fully utilize the functionality of this package requires some of the serivces
to be started and deployed as well. Please refer to the README file within this
package to learn about the options to do that.
"""

import shutil
from pathlib import Path

import yaml
from benedict import benedict

# from . import dlm_db, dlm_ingest, dlm_migration, dlm_request, dlm_storage
from . import dlm_db

__version__ = "0.1.0"

DLM_LIB_DIR = Path(__file__).parent
"""The library install path of dlm."""

DLM_HOME = Path.home() / ".dlm/"
"""The configuration path of dlm."""


def read_config(user_config_file: Path = DLM_HOME / "config.yaml") -> benedict:
    """Read the config file and return the config dictionary."""
    if not user_config_file.exists():
        # create the default user config in DLM_HOME if it does not already exist
        print(f"DLM config file {user_config_file} not found - creating and using default")
        user_config_file.parent.mkdir(exist_ok=True)
        default_user_config_file = DLM_LIB_DIR / "config.yaml"
        shutil.copy(default_user_config_file, user_config_file)

    with open(user_config_file, "r", encoding="utf-8") as file:
        return benedict(yaml.safe_load(file))


CONFIG = read_config()

__all__ = [
    "DLM_HOME",
    "DLM_LIB_DIR",
    "CONFIG",
    "dlm_db",
]
