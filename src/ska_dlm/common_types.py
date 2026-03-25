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


class ChecksumMethod(str, Enum):
    """Allowed checksum algorithms for data objects."""

    NONE = "none"
    ADLER32 = "adler32"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"
    CRC32 = "crc32"
    CRC32C = "crc32c"
    FLETCHER32 = "fletcher32"
    HIGHWAYHASH = "highwayhash"
    JENKINSLOOKUP3 = "jenkinslookup3"
    MD5 = "md5"
    METROHASH128 = "metrohash128"
    SHA1 = "sha1"
    SHA224 = "sha224"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA3_224 = "sha3_224"
    SHA3_256 = "sha3_256"
    SHA3_384 = "sha3_384"
    SHA3_512 = "sha3_512"
    SHA512 = "sha512"
    SHAKE_128 = "shake_128"
    SHAKE_256 = "shake_256"
    SPOOKYHASH = "spookyhash"
    XXH3 = "xxh3"


class MimeType(str, Enum):
    """Common MIME types expected for DLM data records."""

    APPLICATION_FITS = "application/fits"
    APPLICATION_GZIP = "application/gzip"
    APPLICATION_JSON = "application/json"
    APPLICATION_MP4 = "application/mp4"
    APPLICATION_MSWORD = "application/msword"
    APPLICATION_OCTET_STREAM = "application/octet-stream"
    APPLICATION_PDF = "application/pdf"
    APPLICATION_POSTSCRIPT = "application/postscript"
    APPLICATION_RTF = "application/rtf"
    APPLICATION_VND_MS_CAB_COMPRESSED = "application/vnd.ms-cab-compressed"
    APPLICATION_VND_MS_EXCEL = "application/vnd.ms-excel"
    APPLICATION_VND_MS_POWERPOINT = "application/vnd.ms-powerpoint"
    APPLICATION_VND_MSV2 = "application/vnd.msv2"
    APPLICATION_VND_MSV3 = "application/vnd.msv3"
    APPLICATION_VND_MSV4 = "application/vnd.msv4"
    APPLICATION_VND_RAR = "application/vnd.rar"
    APPLICATION_VND_SQLITE3 = "application/vnd.sqlite3"
    APPLICATION_VND_ZARR = "application/vnd.zarr"
    APPLICATION_X_7Z_COMPRESSED = "application/x-7z-compressed"
    APPLICATION_X_BZIP = "application/x-bzip"
    APPLICATION_X_BZIP2 = "application/x-bzip2"
    APPLICATION_X_CPIO = "application/x-cpio"
    APPLICATION_X_DEBIAN_PACKAGE = "application/x-debian-package"
    APPLICATION_X_GZIP = "application/x-gzip"
    APPLICATION_X_HDF = "application/x-hdf"
    APPLICATION_X_ISO9660_IMAGE = "application/x-iso9660-image"
    APPLICATION_X_MS_APPLICATION = "application/x-ms-application"
    APPLICATION_X_MSDOWNLOAD = "application/x-msdownload"
    APPLICATION_X_RAR_COMPRESSED = "application/x-rar-compressed"
    APPLICATION_X_SH = "application/x-sh"
    APPLICATION_X_SHELLSCRIPT = "application/x-shellscript"
    APPLICATION_X_TAR = "application/x-tar"
    APPLICATION_X_TEX = "application/x-tex"
    APPLICATION_X_ZIP_COMPRESSED = "application/x-zip-compressed"
    APPLICATION_XML = "application/xml"
    APPLICATION_YAML = "application/yaml"
    APPLICATION_ZIP = "application/zip"
    AUDIO_MP4 = "audio/mp4"
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_TIFF = "image/tiff"
    TEXT_CSV = "text/csv"
    TEXT_HTML = "text/html"
    TEXT_JAVASCRIPT = "text/javascript"
    TEXT_MARKDOWN = "text/markdown"
    TEXT_PLAIN = "text/plain"
    TEXT_TAB_SEPARATED_VALUES = "text/tab-separated-values"
    TEXT_X_C = "text/x-c"
    TEXT_X_FORTRAN = "text/x-fortran"
    TEXT_X_JAVA_SOURCE = "text/x-java-source"
    TEXT_X_PYTHON = "text/x-python"
    VIDEO_MP4 = "video/mp4"
