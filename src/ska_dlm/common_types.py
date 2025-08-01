"""DLM Storage API module."""

import logging
from enum import Enum

from fastapi import FastAPI

import ska_dlm
from ska_dlm.dlm_db.db_access import DB
from ska_dlm.exception_handling_typer import ExceptionHandlingTyper
from ska_dlm.fastapi_utils import fastapi_auto_annotate


logger = logging.getLogger(__name__)

cli = ExceptionHandlingTyper()
rest = fastapi_auto_annotate(
    FastAPI(
        title="SKA-DLM: Storage Manager REST API",
        description="REST interface of the SKA-DLM Storage Manager",
        version=ska_dlm.__version__,
        license_info={"name": "BSD-3-Clause", "identifier": "BSD-3-Clause"},
    )
)


@rest.get("/storage/query_location_facility", response_model=list[str])
def query_location_facility() -> list[str]:
    """Query the location_facility table for valid facilities."""
    params = {"select": "id"}
    rows = DB.select("location_facility", params=params)
    return [row["id"] for row in rows]


class LocationFacility:
    """Gets allowed location facility values from the database."""

    _valid_values: set[str] = set()
    _loaded = False

    @classmethod
    def _load(cls):
        cls._valid_values = set(query_location_facility())
        cls._loaded = True

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Return True if the given value is a valid location facility."""
        cls._load()
        return value in cls._valid_values

    @classmethod
    def all(cls) -> set[str]:
        """Return all valid location facility values."""
        cls._load()
        return cls._valid_values.copy()


class LocationType(str, Enum):
    """Location type."""

    LOCAL_DEV = "local-dev"
    LOW_INTEGRATION = "low-integration"
    MID_INTEGRATION = "mid-integration"
    LOW_OPERATIONS = "low-operations"
    MID_OPERATIONS = "mid-operations"


class LocationCountry(str, Enum):
    """Location country."""

    AU = "AU"
    ZA = "ZA"
    UK = "UK"


class ConfigType(str, Enum):
    """Config type."""

    RCLONE = "rclone"
    SSH = "ssh"
    AWS = "aws"
    GCS = "gcs"


class StorageType(str, Enum):
    """Storage type."""

    FILESYSTEM = "filesystem"
    OBJECTSTORE = "objectstore"
    TAPE = "tape"


class StorageInterface(str, Enum):
    """Storage interface."""

    POSIX = "posix"
    S3 = "s3"
    SFTP = "sftp"
    HTTPS = "https"


class PhaseType(str, Enum):
    """Phase type / resilience level."""

    GAS = "GAS"
    LIQUID = "LIQUID"
    SOLID = "SOLID"
    PLASMA = "PLASMA"


class ItemType(str, Enum):
    """Data Item on the filesystem."""

    UNKNOWN = "unknown"
    """A single file."""
    FILE = "file"
    """A single file."""
    CONTAINER = "container"
    """A directory superset with parents."""


class ItemState(str, Enum):
    """Item state."""

    INITIALISED = "INITIALISED"
    READY = "READY"
    CORRUPTED = "CORRUPTED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"
