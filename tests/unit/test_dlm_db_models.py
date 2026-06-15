"""Unit tests for DLM SQLAlchemy models."""

import asyncio
import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ska_dlm.dlm_db import (
    ConfigType,
    DataItem,
    ItemState,
    Location,
    LocationCountry,
    LocationFacility,
    LocationType,
    Migration,
    MimeType,
    PhaseType,
    Storage,
    StorageConfig,
    StorageInterface,
    StorageType,
)


def test_table_names():
    """Test table names are correct."""
    assert Location.__tablename__ == "location"
    assert LocationFacility.__tablename__ == "location_facility"
    assert Storage.__tablename__ == "storage"
    assert StorageConfig.__tablename__ == "storage_config"
    assert DataItem.__tablename__ == "data_item"
    assert Migration.__tablename__ == "migration"


@pytest.fixture
async def engine():
    """Create an async engine for testing, using DATABASE_URL."""
    # pylint: disable=invalid-name, too-few-public-methods, not-callable, useless-suppression
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    _engine = create_async_engine(db_url, echo=False)
    yield _engine
    await _engine.dispose()


# pylint: disable=redefined-outer-name
@pytest.fixture
async def session(engine):
    """Create an async session for testing."""
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        future=True,
    )

    async with async_session_factory() as async_session:
        yield async_session

    async with async_session_factory() as async_session:
        # cleanup rows, keep table schema
        pass


# pylint: disable=too-few-public-methods, redefined-outer-name
class TestLocation:
    """Test Location model."""

    @pytest.mark.asyncio
    async def test_create_location(self, session, request):
        """Test creating a Location."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
            location_city="Test City",
        )
        session.add(location)
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        assert location.location_name == "test-location"
        assert location.location_type == LocationType.LOCAL_DEV
        assert location.location_country == LocationCountry.UK
        assert location.location_city == "Test City"
        assert isinstance(location.location_id, uuid.UUID)


# pylint: disable=too-few-public-methods
class TestStorage:
    """Test Storage model."""

    @pytest.mark.asyncio
    async def test_create_storage(self, session, request):
        """Test creating a Storage."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        print(f"Created location with ID: {location.location_id}")

        storage = Storage(
            location_id=location.location_id,
            storage_name="test-storage",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
            storage_phase=PhaseType.GAS,
        )
        session.add(storage)
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(storage)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        assert storage.storage_name == "test-storage"
        assert storage.storage_type == StorageType.FILESYSTEM
        assert storage.storage_interface == StorageInterface.POSIX
        assert storage.storage_phase == PhaseType.GAS
        assert storage.location_id == location.location_id


# pylint: disable=too-few-public-methods
class TestStorageConfig:
    """Test StorageConfig model."""

    @pytest.mark.asyncio
    async def test_create_storage_config(self, session, request):
        """Test creating a StorageConfig."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        storage = Storage(
            location_id=location.location_id,
            storage_name="test-storage",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        session.add(storage)
        await session.commit()

        config = StorageConfig(
            storage_id=storage.storage_id,
            config_type=ConfigType.RCLONE,
            config={"key": "value"},
        )
        session.add(config)
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(config)
                await session.delete(storage)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        assert config.config_type == ConfigType.RCLONE
        assert config.config == {"key": "value"}
        assert config.storage_id == storage.storage_id


# pylint: disable=too-few-public-methods
class TestDataItem:
    """Test DataItem model."""

    @pytest.mark.asyncio
    async def test_create_data_item(self, session, request):
        """Test creating a DataItem."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        storage = Storage(
            location_id=location.location_id,
            storage_name="test-storage",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        session.add(storage)
        await session.commit()

        item = DataItem(
            OID=uuid.uuid4(),
            uri="test-uri",
            item_name="test-item",
            storage_id=storage.storage_id,
            item_mime_type=MimeType.APPLICATION_FITS,
            UID_phase=PhaseType.GAS,
            OID_phase=PhaseType.GAS,
            item_state=ItemState.INITIALISED,
            target_phase=PhaseType.SOLID,
        )
        session.add(item)
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(item)
                await session.delete(storage)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        assert item.item_name == "test-item"
        assert item.item_mime_type == MimeType.APPLICATION_FITS
        assert item.item_state == ItemState.INITIALISED
        assert item.storage_id == storage.storage_id


# pylint: disable=too-few-public-methods
class TestMigration:
    """Test Migration model."""

    @pytest.mark.asyncio
    async def test_create_migration(self, session, request):
        """Test creating a Migration."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        source_storage = Storage(
            location_id=location.location_id,
            storage_name="source-storage",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        dest_storage = Storage(
            location_id=location.location_id,
            storage_name="dest-storage",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        session.add_all([source_storage, dest_storage])
        await session.commit()

        migration = Migration(
            job_id=123,
            oid=uuid.uuid4(),
            url="test-url",
            source_storage_id=source_storage.storage_id,
            destination_storage_id=dest_storage.storage_id,
        )
        session.add(migration)
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(migration)
                await session.delete(source_storage)
                await session.delete(dest_storage)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        assert migration.job_id == 123
        assert migration.source_storage_id == source_storage.storage_id
        assert migration.destination_storage_id == dest_storage.storage_id


class TestRelationships:
    """Test relationships between models."""

    @pytest.mark.asyncio
    async def test_location_has_storages(self, session, request):
        """Test Location to Storage relationship."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        storage1 = Storage(
            location_id=location.location_id,
            storage_name="storage1",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        storage2 = Storage(
            location_id=location.location_id,
            storage_name="storage2",
            storage_type=StorageType.OBJECTSTORE,
            storage_interface=StorageInterface.S3,
        )
        session.add_all([storage1, storage2])
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(storage1)
                await session.delete(storage2)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        # Check storages
        result = await session.execute(
            Storage.__table__.select().where(Storage.location_id == location.location_id)
        )
        storages = result.fetchall()
        assert len(storages) == 2

    @pytest.mark.asyncio
    async def test_storage_has_data_items(self, session, request):
        """Test Storage to DataItem relationship."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        storage = Storage(
            location_id=location.location_id,
            storage_name="test-storage",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        session.add(storage)
        await session.commit()

        data_item1 = DataItem(
            OID=uuid.uuid4(),
            item_name="item1",
            storage_id=storage.storage_id,
            item_state=ItemState.READY,
        )
        data_item2 = DataItem(
            OID=uuid.uuid4(),
            item_name="item2",
            storage_id=storage.storage_id,
            item_state=ItemState.INITIALISED,
        )
        session.add_all([data_item1, data_item2])
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(data_item1)
                await session.delete(data_item2)
                await session.delete(storage)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        # Check data items
        result = await session.execute(
            DataItem.__table__.select().where(DataItem.storage_id == storage.storage_id)
        )
        data_items = result.fetchall()
        assert len(data_items) == 2

    @pytest.mark.asyncio
    async def test_storage_has_config(self, session, request):
        """Test Storage to StorageConfig relationship."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        storage = Storage(
            location_id=location.location_id,
            storage_name="test-storage",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        session.add(storage)
        await session.commit()

        config = StorageConfig(
            storage_id=storage.storage_id,
            config_type=ConfigType.RCLONE,
            config={"rclone_config": "data"},
        )
        session.add(config)
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(config)
                await session.delete(storage)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        # Check config
        result = await session.execute(
            StorageConfig.__table__.select().where(StorageConfig.storage_id == storage.storage_id)
        )
        storage_config = result.first()
        assert storage_config is not None
        assert storage_config.config_type == ConfigType.RCLONE

    @pytest.mark.asyncio
    async def test_location_facility_has_locations(self, session, request):
        """Test LocationFacility to Location relationship."""
        loop = asyncio.get_running_loop()
        facility = LocationFacility(id="test-facility")
        session.add(facility)
        await session.commit()

        location1 = Location(
            location_name="loc1",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
            location_facility=facility.id,
        )
        location2 = Location(
            location_name="loc2",
            location_type=LocationType.MID_INTEGRATION,
            location_country=LocationCountry.AU,
            location_facility=facility.id,
        )
        session.add_all([location1, location2])
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(location1)
                await session.delete(location2)
                await session.delete(facility)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        # Check locations
        result = await session.execute(
            Location.__table__.select().where(Location.location_facility == facility.id)
        )
        locations = result.fetchall()
        assert len(locations) == 2

    @pytest.mark.asyncio
    async def test_migration_has_storages(self, session, request):
        """Test Migration relationships to storages."""
        loop = asyncio.get_running_loop()
        location = Location(
            location_name="test-location",
            location_type=LocationType.LOCAL_DEV,
            location_country=LocationCountry.UK,
        )
        session.add(location)
        await session.commit()

        source = Storage(
            location_id=location.location_id,
            storage_name="source",
            storage_type=StorageType.FILESYSTEM,
            storage_interface=StorageInterface.POSIX,
        )
        dest = Storage(
            location_id=location.location_id,
            storage_name="dest",
            storage_type=StorageType.OBJECTSTORE,
            storage_interface=StorageInterface.S3,
        )
        session.add_all([source, dest])
        await session.commit()

        migration = Migration(
            job_id=456,
            oid=uuid.uuid4(),
            url="migration-url",
            source_storage_id=source.storage_id,
            destination_storage_id=dest.storage_id,
        )
        session.add(migration)
        await session.commit()

        def cleanup():
            async def async_cleanup():
                await session.delete(migration)
                await session.delete(source)
                await session.delete(dest)
                await session.delete(location)
                await session.commit()

            loop.run_until_complete(async_cleanup())

        # Register the teardown function
        request.addfinalizer(cleanup)

        # Check migration storages
        result = await session.execute(Migration.__table__.select().where(Migration.job_id == 456))
        mig = result.first()
        assert mig.source_storage_id == source.storage_id
        assert mig.destination_storage_id == dest.storage_id
