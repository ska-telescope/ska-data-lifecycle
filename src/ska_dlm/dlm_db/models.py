"""SQLAlchemy models for DLM database tables."""
from enum import Enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .orm import Base


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class LocationType(str, Enum):
    """Enumeration of location environments used by DLM."""

    local_dev = "local-dev"
    low_integration = "low-integration"
    mid_integration = "mid-integration"
    low_operations = "low-operations"
    mid_operations = "mid-operations"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class LocationCountry(str, Enum):
    """Enumeration of country codes for locations."""

    AU = "AU"
    ZA = "ZA"
    UK = "UK"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class ConfigType(str, Enum):
    """Supported secure access configuration transport protocols."""

    rclone = "rclone"
    ssh = "ssh"
    aws = "aws"
    gcs = "gcs"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class StorageType(str, Enum):
    """Type of storage layer: filesystem, object store, or tape."""

    filesystem = "filesystem"
    objectstore = "objectstore"
    tape = "tape"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class StorageInterface(str, Enum):
    """Storage protocol/interface type used by each storage endpoint."""

    posix = "posix"
    s3 = "s3"
    sftp = "sftp"
    https = "https"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class PhaseType(str, Enum):
    """Physical phase used to model database lifecycle stages."""

    GAS = "GAS"
    LIQUID = "LIQUID"
    SOLID = "SOLID"
    PLASMA = "PLASMA"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class ItemState(str, Enum):
    """Lifecycle state of a data item in DLM."""

    INITIALISED = "INITIALISED"
    READY = "READY"
    CORRUPTED = "CORRUPTED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class ChecksumMethod(str, Enum):
    """Allowed checksum algorithms for data objects."""

    none = "none"
    adler32 = "adler32"
    blake2b = "blake2b"
    blake2s = "blake2s"
    crc32 = "crc32"
    crc32c = "crc32c"
    fletcher32 = "fletcher32"
    highwayhash = "highwayhash"
    jenkinslookup3 = "jenkinslookup3"
    md5 = "md5"
    metrohash128 = "metrohash128"
    sha1 = "sha1"
    sha224 = "sha224"
    sha256 = "sha256"
    sha384 = "sha384"
    sha3_224 = "sha3_224"
    sha3_256 = "sha3_256"
    sha3_384 = "sha3_384"
    sha3_512 = "sha3_512"
    sha512 = "sha512"
    shake_128 = "shake_128"
    shake_256 = "shake_256"
    spookyhash = "spookyhash"
    xxh3 = "xxh3"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class MimeType(str, Enum):
    """Common MIME types expected for DLM data records."""

    application_fits = "application/fits"
    application_gzip = "application/gzip"
    application_json = "application/json"
    application_mp4 = "application/mp4"
    application_msword = "application/msword"
    application_octet_stream = "application/octet-stream"
    application_pdf = "application/pdf"
    application_postscript = "application/postscript"
    application_rtf = "application/rtf"
    application_vnd_ms_cab_compressed = "application/vnd.ms-cab-compressed"
    application_vnd_ms_excel = "application/vnd.ms-excel"
    application_vnd_ms_powerpoint = "application/vnd.ms-powerpoint"
    application_vnd_msv2 = "application/vnd.msv2"
    application_vnd_msv3 = "application/vnd.msv3"
    application_vnd_msv4 = "application/vnd.msv4"
    application_vnd_rar = "application/vnd.rar"
    application_vnd_sqlite3 = "application/vnd.sqlite3"
    application_vnd_zarr = "application/vnd.zarr"
    application_x_7z_compressed = "application/x-7z-compressed"
    application_x_bzip = "application/x-bzip"
    application_x_bzip2 = "application/x-bzip2"
    application_x_cpio = "application/x-cpio"
    application_x_debian_package = "application/x-debian-package"
    application_x_gzip = "application/x-gzip"
    application_x_hdf = "application/x-hdf"
    application_x_iso9660_image = "application/x-iso9660-image"
    application_x_ms_application = "application/x-ms-application"
    application_x_msdownload = "application/x-msdownload"
    application_x_rar_compressed = "application/x-rar-compressed"
    application_x_sh = "application/x-sh"
    application_x_shellscript = "application/x-shellscript"
    application_x_tar = "application/x-tar"
    application_x_tex = "application/x-tex"
    application_x_zip_compressed = "application/x-zip-compressed"
    application_xml = "application/xml"
    application_yaml = "application/yaml"
    application_zip = "application/zip"
    audio_mp4 = "audio/mp4"
    image_jpeg = "image/jpeg"
    image_png = "image/png"
    image_tiff = "image/tiff"
    text_csv = "text/csv"
    text_html = "text/html"
    text_javascript = "text/javascript"
    text_markdown = "text/markdown"
    text_plain = "text/plain"
    text_tab_separated_values = "text/tab-separated-values"
    text_x_c = "text/x-c"
    text_x_fortran = "text/x-fortran"
    text_x_java_source = "text/x-java-source"
    text_x_python = "text/x-python"
    video_mp4 = "video/mp4"


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class LocationFacility(Base):
    """Represents a facility associated with storage locations in DLM."""

    __tablename__ = "location_facility"
    __table_args__ = {"schema": "dlm"}

    id = Column(String, primary_key=True)
    locations = relationship("Location", back_populates="facility")


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class Location(Base):
    """Represents a storage location record in the DLM schema."""

    __tablename__ = "location"
    __table_args__ = {"schema": "dlm"}

    location_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    location_name = Column(String, nullable=False, unique=True)
    location_type = Column(
        SAEnum(
            LocationType,
            name="location_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    location_country = Column(
        SAEnum(
            LocationCountry,
            name="location_country",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )
    location_city = Column(String, nullable=True)
    location_facility = Column(String, ForeignKey("dlm.location_facility.id"), nullable=True)
    location_check_url = Column(String, nullable=True)
    location_last_check = Column(DateTime(timezone=False), nullable=True)
    location_date = Column(DateTime(timezone=False), nullable=False, server_default=func.now())

    facility = relationship("LocationFacility", back_populates="locations")


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class Storage(Base):
    """Represents a storage endpoint for DLM operations."""

    __tablename__ = "storage"
    __table_args__ = {"schema": "dlm"}

    storage_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    location_id = Column(
        UUID(as_uuid=True), ForeignKey("dlm.location.location_id"), nullable=False
    )
    storage_name = Column(String, nullable=False, unique=True)
    root_directory = Column(String, nullable=True)
    storage_type = Column(
        SAEnum(
            StorageType,
            name="storage_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    storage_interface = Column(
        SAEnum(
            StorageInterface,
            name="storage_interface",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    storage_phase = Column(
        SAEnum(
            PhaseType,
            name="phase_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        server_default="GAS",
    )
    storage_capacity = Column(BigInteger, default=-1)
    storage_use_pct = Column(Numeric(3, 1), default=0.0)
    storage_permissions = Column(String, default="RW")
    storage_checked = Column(Boolean, default=False)
    storage_check_url = Column(String, nullable=True)
    storage_last_checked = Column(DateTime(timezone=False), nullable=True)
    storage_num_objects = Column(BigInteger, default=0)
    storage_available = Column(Boolean, default=True)
    storage_retired = Column(Boolean, default=False)
    storage_retire_date = Column(DateTime(timezone=False), nullable=True)
    storage_date = Column(DateTime(timezone=False), nullable=False, server_default=func.now())

    location = relationship("Location")
    config = relationship("StorageConfig", back_populates="storage", uselist=False)
    data_items = relationship("DataItem", back_populates="storage")


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class StorageConfig(Base):
    """Represents per-storage JSON configuration metadata."""

    __tablename__ = "storage_config"
    __table_args__ = {"schema": "dlm"}

    config_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    storage_id = Column(UUID(as_uuid=True), ForeignKey("dlm.storage.storage_id"), nullable=False)
    config_type = Column(
        SAEnum(
            ConfigType,
            name="config_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="rclone",
    )
    config = Column(JSONB, nullable=False)
    config_date = Column(DateTime(timezone=False), nullable=False, server_default=func.now())

    storage = relationship("Storage", back_populates="config")


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class DataItem(Base):
    """Represents a DLM data item and its lifecycle state."""

    __tablename__ = "data_item"
    __table_args__ = {"schema": "dlm"}

    UID = Column(
        "uid", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    OID = Column("oid", UUID(as_uuid=True), nullable=True)
    item_version = Column(Integer, default=1)
    item_name = Column(String, nullable=True)
    item_tags = Column(JSONB, nullable=True)
    storage_id = Column(UUID(as_uuid=True), ForeignKey("dlm.storage.storage_id"), nullable=True)
    uri = Column(String, nullable=True, default="inline://item_value")
    item_value = Column(Text, nullable=True, default="")
    item_type = Column(String, nullable=False, default="file")
    item_format = Column(String, nullable=False, default="unknown")
    item_encoding = Column(String, nullable=False, default="unknown")
    item_mime_type = Column(
        SAEnum(
            MimeType,
            name="mime_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="application/octet-stream",
    )
    item_level = Column(Integer, nullable=False, default=-1)
    UID_phase = Column(
        "uid_phase",
        SAEnum(
            PhaseType,
            name="phase_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="GAS",
    )
    OID_phase = Column(
        "oid_phase",
        SAEnum(
            PhaseType,
            name="phase_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="GAS",
    )
    item_state = Column(
        SAEnum(
            ItemState,
            name="item_state",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="INITIALISED",
    )
    target_phase = Column(
        SAEnum(
            PhaseType,
            name="phase_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="SOLID",
    )
    UID_creation = Column(
        "uid_creation", DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    OID_creation = Column("oid_creation", DateTime(timezone=False), nullable=True)
    UID_expiration = Column(
        "uid_expiration", DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    OID_expiration = Column(
        "oid_expiration",
        DateTime(timezone=False),
        nullable=False,
        server_default=text("'2099-12-31 23:59:59'"),
    )
    UID_deletion = Column("uid_deletion", DateTime(timezone=False), nullable=True)
    OID_deletion = Column("oid_deletion", DateTime(timezone=False), nullable=True)
    expired = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    last_access = Column(DateTime(timezone=False), nullable=True)
    item_checksum = Column(String, nullable=True)
    checksum_method = Column(
        SAEnum(
            ChecksumMethod,
            name="checksum_method",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="none",
    )
    last_check = Column(DateTime(timezone=False), nullable=True)
    item_owner = Column(String, nullable=False, default="SKA")
    item_group = Column(String, nullable=False, default="SKA")
    ACL = Column("acl", JSONB, nullable=True)
    activate_method = Column(String, nullable=True)
    item_size = Column(Integer, nullable=True)
    decompressed_size = Column(Integer, nullable=True)
    compression_method = Column(String, nullable=True)
    parents = Column(UUID(as_uuid=True), nullable=True)
    children = Column(UUID(as_uuid=True), nullable=True)
    item_metadata = Column("metadata", JSONB, nullable=True)  # SQL column name is metadata

    storage = relationship("Storage", back_populates="data_items")


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class PhaseChange(Base):
    """Represents a phase-change request for a data item."""

    __tablename__ = "phase_change"
    __table_args__ = {"schema": "dlm"}

    phase_change_id = Column(BigInteger, primary_key=True)
    oid = Column(UUID(as_uuid=True), nullable=False)
    requested_phase = Column(
        SAEnum(
            PhaseType,
            name="phase_type",
            schema="dlm",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default="GAS",
    )
    request_creation = Column(DateTime(timezone=False), nullable=False, server_default=func.now())


# pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
class Migration(Base):
    """Tracks file migration job details in DLM."""

    __tablename__ = "migration"
    __table_args__ = {"schema": "dlm"}

    migration_id = Column(BigInteger, primary_key=True)
    job_id = Column(BigInteger, nullable=False)
    oid = Column(UUID(as_uuid=True), nullable=False)
    url = Column(String, nullable=False)
    source_storage_id = Column(
        UUID(as_uuid=True), ForeignKey("dlm.storage.storage_id"), nullable=False
    )
    destination_storage_id = Column(
        UUID(as_uuid=True), ForeignKey("dlm.storage.storage_id"), nullable=False
    )
    user = Column(String, nullable=False, default="SKA")
    group = Column(String, nullable=False, default="SKA")
    job_status = Column(JSONB, nullable=True)
    job_stats = Column(JSONB, nullable=True)
    complete = Column(Boolean, default=False)
    date = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    completion_date = Column(DateTime(timezone=False), nullable=True)
    command = Column(String, nullable=True)

    source_storage = relationship("Storage", foreign_keys=[source_storage_id])
    destination_storage = relationship("Storage", foreign_keys=[destination_storage_id])
