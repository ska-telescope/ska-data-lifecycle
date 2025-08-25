"""DLM Storage API module."""
# Refer to https://confluence.skatelescope.org/pages/viewpage.action?pageId=330648807
# for additional details.
from enum import Enum


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

    # Undetermined type
    UNKNOWN = "unknown"
    # A single file
    FILE = "file"
    # A directory superset with parents
    CONTAINER = "container"


class ItemState(str, Enum):
    """Item state."""

    INITIALISED = "INITIALISED"
    READY = "READY"
    CORRUPTED = "CORRUPTED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"
