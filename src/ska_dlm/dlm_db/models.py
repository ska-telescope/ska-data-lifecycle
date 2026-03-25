"""SQLAlchemy models for DLM database tables."""

from sqlalchemy import BigInteger, Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ska_dlm.common_types import (
    ChecksumMethod,
    ConfigType,
    ItemState,
    LocationCountry,
    LocationType,
    MimeType,
    PhaseType,
    StorageInterface,
    StorageType,
)

from .orm import Base


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
