from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKeyConstraint, Identity, Index, Integer, JSON, Numeric, PrimaryKeyConstraint, SmallInteger, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime
import decimal
import uuid

class Base(DeclarativeBase):
    pass


class Location(Base):
    __tablename__ = 'location'
    __table_args__ = (
        PrimaryKeyConstraint('location_id', name='location_pkey'),
        UniqueConstraint('location_name', name='location_location_name_key')
    )

    location_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    location_name: Mapped[str] = mapped_column(String)
    location_type: Mapped[str] = mapped_column(String)
    location_country: Mapped[Optional[str]] = mapped_column(String)
    location_city: Mapped[Optional[str]] = mapped_column(String)
    location_facility: Mapped[Optional[str]] = mapped_column(String)
    location_check_url: Mapped[Optional[str]] = mapped_column(String)
    location_last_check: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    location_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    storage: Mapped[List['Storage']] = relationship('Storage', back_populates='location')


class PhaseChange(Base):
    __tablename__ = 'phase_change'
    __table_args__ = (
        PrimaryKeyConstraint('phase_change_id', name='phase_change_pkey'),
    )

    phase_change_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True, start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    oid: Mapped[uuid.UUID] = mapped_column(Uuid)
    requested_phase: Mapped[Optional[str]] = mapped_column(String, server_default=text("'GAS'::character varying"))
    request_creation: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))


class Storage(Base):
    __tablename__ = 'storage'
    __table_args__ = (
        ForeignKeyConstraint(['location_id'], ['location.location_id'], ondelete='SET NULL', name='fk_location'),
        PrimaryKeyConstraint('storage_id', name='storage_pkey'),
        UniqueConstraint('storage_name', name='storage_storage_name_key')
    )

    storage_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    location_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    storage_name: Mapped[str] = mapped_column(String)
    storage_type: Mapped[str] = mapped_column(String)
    storage_interface: Mapped[str] = mapped_column(String)
    root_directory: Mapped[Optional[str]] = mapped_column(String)
    storage_phase: Mapped[Optional[str]] = mapped_column(String, server_default=text("'GAS'::character varying"))
    storage_capacity: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text("'-1'::integer"))
    storage_use_pct: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(3, 1), server_default=text('0.0'))
    storage_permissions: Mapped[Optional[str]] = mapped_column(String, server_default=text("'RW'::character varying"))
    storage_checked: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    storage_check_url: Mapped[Optional[str]] = mapped_column(String)
    storage_last_checked: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    storage_num_objects: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))
    storage_available: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    storage_retired: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    storage_retire_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    storage_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    location: Mapped['Location'] = relationship('Location', back_populates='storage')
    data_item: Mapped[List['DataItem']] = relationship('DataItem', back_populates='storage')
    migration: Mapped[List['Migration']] = relationship('Migration', foreign_keys='[Migration.destination_storage_id]', back_populates='destination_storage')
    migration_: Mapped[List['Migration']] = relationship('Migration', foreign_keys='[Migration.source_storage_id]', back_populates='source_storage')
    storage_config: Mapped[List['StorageConfig']] = relationship('StorageConfig', back_populates='storage')


class DataItem(Base):
    __tablename__ = 'data_item'
    __table_args__ = (
        ForeignKeyConstraint(['storage_id'], ['storage.storage_id'], ondelete='SET NULL', name='fk_storage'),
        PrimaryKeyConstraint('uid', name='data_item_pkey'),
        Index('idx_fk_storage_id', 'storage_id'),
        Index('idx_unq_oid_uid_item_version', 'oid', 'uid', 'item_version', unique=True)
    )

    uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    oid: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    item_version: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('1'))
    item_name: Mapped[Optional[str]] = mapped_column(String)
    item_tags: Mapped[Optional[dict]] = mapped_column(JSON)
    storage_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    uri: Mapped[Optional[str]] = mapped_column(String, server_default=text("'inline://item_value'::character varying"))
    item_value: Mapped[Optional[str]] = mapped_column(Text, server_default=text("''::text"))
    item_type: Mapped[Optional[str]] = mapped_column(String, server_default=text("'file'::character varying"))
    item_format: Mapped[Optional[str]] = mapped_column(String, server_default=text("'unknown'::character varying"))
    item_encoding: Mapped[Optional[str]] = mapped_column(String, server_default=text("'unknown'::character varying"))
    item_mime_type: Mapped[Optional[str]] = mapped_column(String, server_default=text("'application/octet-stream'::character varying"))
    item_level: Mapped[Optional[int]] = mapped_column(SmallInteger, server_default=text("'-1'::integer"))
    uid_phase: Mapped[Optional[str]] = mapped_column(String, server_default=text("'GAS'::character varying"))
    oid_phase: Mapped[Optional[str]] = mapped_column(String, server_default=text("'GAS'::character varying"))
    item_state: Mapped[Optional[str]] = mapped_column(String, server_default=text("'INITIALIZED'::character varying"))
    uid_creation: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    oid_creation: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    uid_expiration: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text("(now() + ('24:00:00'::time without time zone)::interval)"))
    oid_expiration: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text("'2099-12-31 23:59:59'::timestamp without time zone"))
    uid_deletion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    oid_deletion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    expired: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    deleted: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    last_access: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    item_checksum: Mapped[Optional[str]] = mapped_column(String)
    checksum_method: Mapped[Optional[str]] = mapped_column(String, server_default=text("'none'::character varying"))
    last_check: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    item_owner: Mapped[Optional[str]] = mapped_column(String, server_default=text("'SKA'::character varying"))
    item_group: Mapped[Optional[str]] = mapped_column(String, server_default=text("'SKA'::character varying"))
    acl: Mapped[Optional[dict]] = mapped_column(JSON)
    activate_method: Mapped[Optional[str]] = mapped_column(String)
    item_size: Mapped[Optional[int]] = mapped_column(Integer)
    decompressed_size: Mapped[Optional[int]] = mapped_column(Integer)
    compression_method: Mapped[Optional[str]] = mapped_column(String)
    parents: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    children: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    metadata_: Mapped[Optional[dict]] = mapped_column('metadata', JSONB)

    storage: Mapped[Optional['Storage']] = relationship('Storage', back_populates='data_item')


class Migration(Base):
    __tablename__ = 'migration'
    __table_args__ = (
        ForeignKeyConstraint(['destination_storage_id'], ['storage.storage_id'], ondelete='SET NULL', name='fk_destination_storage'),
        ForeignKeyConstraint(['source_storage_id'], ['storage.storage_id'], ondelete='SET NULL', name='fk_source_storage'),
        PrimaryKeyConstraint('migration_id', name='migration_pkey')
    )

    migration_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True, start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    job_id: Mapped[int] = mapped_column(BigInteger)
    oid: Mapped[uuid.UUID] = mapped_column(Uuid)
    url: Mapped[str] = mapped_column(String)
    source_storage_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    destination_storage_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    user: Mapped[Optional[str]] = mapped_column(String, server_default=text("'SKA'::character varying"))
    group: Mapped[Optional[str]] = mapped_column(String, server_default=text("'SKA'::character varying"))
    job_status: Mapped[Optional[dict]] = mapped_column(JSONB)
    job_stats: Mapped[Optional[dict]] = mapped_column(JSONB)
    complete: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    completion_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    destination_storage: Mapped['Storage'] = relationship('Storage', foreign_keys=[destination_storage_id], back_populates='migration')
    source_storage: Mapped['Storage'] = relationship('Storage', foreign_keys=[source_storage_id], back_populates='migration_')


class StorageConfig(Base):
    __tablename__ = 'storage_config'
    __table_args__ = (
        ForeignKeyConstraint(['storage_id'], ['storage.storage_id'], ondelete='SET NULL', name='fk_cfg_storage_id'),
        PrimaryKeyConstraint('config_id', name='storage_config_pkey')
    )

    config_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    storage_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    config: Mapped[dict] = mapped_column(JSON)
    config_type: Mapped[Optional[str]] = mapped_column(String, server_default=text("'rclone'::character varying"))
    config_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    storage: Mapped['Storage'] = relationship('Storage', back_populates='storage_config')
