#!/usr/bin/env python

"""Tests for `ska_data_lifecycle` module."""

import asyncio
import datetime

import inflect
import pytest

from ska_dlm import CONFIG, data_item
from ska_dlm.dlm_db.db_access import DB
from ska_dlm.dlm_ingest.dlm_ingest_requests import ItemType
from ska_dlm.dlm_migration.dlm_migration_requests import (
    _get_migration_record,
    update_migration_statuses,
)
from ska_dlm.dlm_storage.main import persist_new_data_items
from ska_dlm.exceptions import InvalidQueryParameters, ValueAlreadyInDB
from tests.common_local import DlmTestClientLocal
from tests.integration.client.dlm_gateway_client import get_token
from tests.test_env import DlmTestClient

ROOT = "/data/"
RCLONE_TEST_FILE_PATH = "/data/MyDisk/testfile"
TEST_URI = "testfile"
ROOT_DIRECTORY1 = "/data/MyDisk/"
ROOT_DIRECTORY2 = "/data/MyDisk2/"

"""A file that is available locally in the rclone container"""
RCLONE_TEST_FILE_CONTENT = "license content"
RCLONE_TEST_FILE_SIZE = 15  # bytes
TODAY_DATE = datetime.datetime.now()
METADATA_RECEIVED = {
    "execution_block": "eb-meta-20240723-00000",
}


def _clear_database():
    DB.delete(CONFIG.DLM.migration_table)
    DB.delete(CONFIG.DLM.dlm_table)
    DB.delete(CONFIG.DLM.storage_config_table)
    DB.delete(CONFIG.DLM.storage_table)
    DB.delete(CONFIG.DLM.location_table)


@pytest.fixture(name="auth", scope="session", autouse=True)
def setup_auth(env, request):
    """Initialise Auth per session."""
    # this should only run once per test suite
    if request.config.getoption("--auth"):
        token = get_token("admin", "admin", env.get_gateway_url())
        token = token["access_token"]
        env.request_requests.TOKEN = token
        env.data_item_requests.TOKEN = token
        env.ingest_requests.TOKEN = token
        env.storage_requests.TOKEN = token
        env.migration_requests.TOKEN = token


@pytest.fixture(scope="function", autouse=True)
def setup(env):
    """Initialise test storage and rclone configuration."""
    _clear_database()

    env.write_rclone_file_content(RCLONE_TEST_FILE_PATH, RCLONE_TEST_FILE_CONTENT)

    # we need a location to register the storage
    location_id = env.storage_requests.init_location("MyOwnStorage", "local-dev")
    uuid = env.storage_requests.init_storage(
        storage_name="MyDisk",
        root_directory=ROOT_DIRECTORY1,
        location_id=location_id,
        storage_type="filesystem",
        storage_interface="posix",
        storage_capacity=100000000,
    )
    config = {"name": "MyDisk", "root_path": "/", "type": "alias", "parameters": {"remote": "/"}}
    env.storage_requests.create_storage_config(storage_id=uuid, config=config)
    # configure rclone
    env.storage_requests.create_rclone_config(config)
    yield
    _clear_database()
    env.clear_rclone_data(ROOT)


def __initialise_data_item(env):
    """Test data_item init."""
    engine = inflect.engine()
    success = True
    for i in range(1, 51, 1):
        ordinal = engine.number_to_words(engine.ordinal(i))
        uid = env.ingest_requests.init_data_item(f"this/is/the/{ordinal}/test/item")
        if uid is None:
            success = False
    assert success


@pytest.mark.integration_test
@pytest.mark.skip(reason="Placeholder. We removed the ingest_data_item alias.")
def test_ingest_data_item(env):
    """Test the ingest_data_item function."""
    uid = env.ingest_requests.register_data_item(
        item_name="/my/ingest/test/item", uri=TEST_URI, storage_name="MyDisk", metadata=None
    )
    assert len(uid) == 36


@pytest.mark.integration_test
def test_register_data_item_with_metadata(env):
    """Test the register_data_item function with provided metadata."""
    uid = env.ingest_requests.register_data_item(
        item_name="/my/ingest/test/item2",
        uri=TEST_URI,
        storage_name="MyDisk",
        metadata=METADATA_RECEIVED,
    )
    assert len(uid) == 36
    with pytest.raises(ValueAlreadyInDB, match="Item is already registered"):
        env.ingest_requests.register_data_item(
            item_name="/my/ingest/test/item2",
            uri=TEST_URI,
            storage_name="MyDisk",
            metadata=METADATA_RECEIVED,
        )


@pytest.mark.integration_test
def test_query_expired_empty(env):
    """Test the query expired returning an empty set."""
    result = env.request_requests.query_expired()
    assert len(result) == 0


@pytest.mark.integration_test
def test_query_expired(env):
    """Test the query expired returning records."""
    if not isinstance(env, DlmTestClientLocal):
        pytest.skip("Unprocessable Entity")

    __initialise_data_item(env)
    uid = env.data_item_requests.query_data_item()[0]["uid"]
    offset = datetime.timedelta(days=1)
    data_item.set_state(uid=uid, state="READY")
    result = env.request_requests.query_expired(offset)
    assert len(result) != 0


@pytest.mark.integration_test
def test_location_init(env):
    """Test initialisation on a location."""
    env.storage_requests.init_location("TestLocation", "low-integration")
    location = env.storage_requests.query_location(location_name="TestLocation")[0]
    assert location["location_type"] == "low-integration"


@pytest.mark.integration_test
def test_set_uri_state_phase(env):
    """Update a data_item record with the pointer to a file."""
    uid = env.ingest_requests.init_data_item(item_name="this/is/the/first/test/item")
    storage_id = env.storage_requests.query_storage(storage_name="MyDisk")[0]["storage_id"]
    data_item.set_uri(uid, TEST_URI, storage_id)
    assert env.data_item_requests.query_data_item(uid=uid)[0]["uri"] == TEST_URI
    data_item.set_state(uid, "READY")
    data_item.set_phase(uid, "PLASMA")
    items = env.data_item_requests.query_data_item(uid=uid)
    assert len(items) == 1
    assert items[0]["item_state"] == "READY"
    assert items[0]["uid_phase"] == "PLASMA"


# TODO: We don't want RCLONE_TEST_FILE_PATH to disappear after one test run.
@pytest.mark.integration_test
def test_delete_item_payload(env):
    """Delete the payload of a data_item."""
    fpath = TEST_URI
    storage_id = env.storage_requests.query_storage(storage_name="MyDisk")[0]["storage_id"]
    uid = env.ingest_requests.register_data_item(item_name=fpath, uri=fpath, storage_name="MyDisk")
    data_item.set_state(uid, "READY")
    data_item.set_uri(uid, fpath, storage_id)
    queried_uid = env.data_item_requests.query_data_item(item_name=fpath)[0]["uid"]
    assert uid == queried_uid

    # TODO: not a client endpoint
    # pylint: disable-next=import-outside-toplevel
    from ska_dlm.dlm_storage.dlm_storage_requests import delete_data_item_payload

    delete_data_item_payload(uid)
    assert env.data_item_requests.query_data_item(item_name=fpath)[0]["uri"] == fpath
    assert env.data_item_requests.query_data_item(item_name=fpath)[0]["item_state"] == "DELETED"


def __initialise_storage_config(env):
    """Add a new location, storage and configuration to the rclone server."""
    env.create_rclone_directory(ROOT_DIRECTORY2)
    location = env.storage_requests.query_location("MyHost")
    if location:
        location_id = location[0]["location_id"]
    else:
        location_id = env.storage_requests.init_location("MyHost", "low-integration")
    assert len(location_id) == 36
    config = {"name": "MyDisk2", "root_path": "/", "type": "alias", "parameters": {"remote": "/"}}
    uuid = env.storage_requests.init_storage(
        storage_name="MyDisk2",
        root_directory=ROOT_DIRECTORY2,
        location_id=location_id,
        storage_type="filesystem",
        storage_interface="posix",
        storage_capacity=100000000,
    )
    assert len(uuid) == 36
    config_id = env.storage_requests.create_storage_config(storage_id=uuid, config=config)
    assert len(config_id) == 36
    # configure rclone
    assert env.storage_requests.create_rclone_config(config) is True


@pytest.mark.integration_test
def test_copy(env: DlmTestClient):
    """Copy a test file from one storage to another."""
    # NOTE: this test will not work without requests being made via a gateway

    if isinstance(env, DlmTestClientLocal):
        pytest.skip("Unprocessable Entity")

    __initialise_storage_config(env)
    dest_id = env.storage_requests.query_storage("MyDisk2")[0]["storage_id"]
    uid = env.ingest_requests.register_data_item(
        item_name="/my/ingest/test/item2", uri=TEST_URI, storage_name="MyDisk"
    )
    assert len(uid) == 36
    dest = "testfile_copy"
    results = env.migration_requests.copy_data_item(uid=uid, destination_id=dest_id, path=dest)
    assert RCLONE_TEST_FILE_CONTENT == env.get_rclone_local_file_content(RCLONE_TEST_FILE_PATH)

    # trigger manual update of migrations status
    asyncio.run(update_migration_statuses())

    # check that a query for all migrations returns the details of this single migration
    result = _get_migration_record(results["migration_id"])

    assert len(result) == 1
    assert result[0]["destination_storage_id"] == dest_id
    assert result[0]["complete"] is True
    assert result[0]["job_status"]["finished"] is True
    assert result[0]["job_stats"]["bytes"] == RCLONE_TEST_FILE_SIZE

    # test the query_migration function
    yesterday = (TODAY_DATE - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    result = env.migration_requests.query_migrations(start_date=yesterday, storage_id=dest_id)
    assert len(result) == 1
    # a query for migrations made up until yesterday should return nothing
    query_result = env.migration_requests.query_migrations(end_date=yesterday)
    assert query_result == []


@pytest.mark.integration_test
def test_copy_container(env):
    """Copy a container from one storage to another."""
    # NOTE: this test will not work without requests being made via a gateway

    if isinstance(env, DlmTestClientLocal):
        pytest.skip("Unprocessable Entity")

    __initialise_storage_config(env)

    file1_data = "Some data"
    file2_data = "More data"

    env.create_rclone_directory(f"{ROOT_DIRECTORY1}/container/dir1")
    env.write_rclone_file_content(f"{ROOT_DIRECTORY1}/container/file1", file1_data)
    env.write_rclone_file_content(f"{ROOT_DIRECTORY1}/container/dir1/file2", file2_data)

    dest_id = env.storage_requests.query_storage("MyDisk2")[0]["storage_id"]

    uid_root = env.ingest_requests.register_data_item(
        item_name="container",
        uri="container/",
        item_type=ItemType.CONTAINER,
        storage_name="MyDisk",
        parents=None,
    )
    assert len(uid_root) == 36

    dir1_uid = env.ingest_requests.register_data_item(
        item_name="container/dir1",
        uri="container/dir1",
        item_type=ItemType.CONTAINER,
        storage_name="MyDisk",
        parents=uid_root,
    )
    assert len(dir1_uid) == 36

    file1_uid = env.ingest_requests.register_data_item(
        item_name="container/file1",
        uri="container/file1",
        item_type=ItemType.FILE,
        storage_name="MyDisk",
        parents=uid_root,
    )
    assert len(file1_uid) == 36

    file2_uid = env.ingest_requests.register_data_item(
        item_name="container/dir1/file2",
        uri="container/dir1/file2",
        item_type=ItemType.FILE,
        storage_name="MyDisk",
        parents=dir1_uid,
    )
    assert len(file2_uid) == 36

    dest = "container"
    result = env.migration_requests.copy_data_item(uid=uid_root, destination_id=dest_id, path=dest)

    # trigger manual update of migrations status
    asyncio.run(update_migration_statuses())

    # check that a query for all migrations returns the details of this single migration
    result = _get_migration_record(result["migration_id"])

    assert len(result) == 1
    assert result[0]["destination_storage_id"] == dest_id
    assert result[0]["complete"] is True
    assert result[0]["job_status"]["finished"] is True
    assert result[0]["job_stats"]["bytes"] == len(file1_data) + len(file2_data)


@pytest.mark.integration_test
def test_update_item_tags(env):
    """Update the item_tags field of a data_item."""
    _ = env.ingest_requests.register_data_item(
        item_name="/my/ingest/test/item2", uri=TEST_URI, storage_name="MyDisk"
    )
    res = env.data_item_requests.update_item_tags(
        "/my/ingest/test/item2", item_tags={"a": "SKA", "b": "DLM", "c": "dummy"}
    )
    assert res
    res = env.data_item_requests.update_item_tags(
        "/my/ingest/test/item2", item_tags={"c": "Hello", "d": "World"}
    )
    assert res
    tags = env.data_item_requests.query_data_item(item_name="/my/ingest/test/item2")[0][
        "item_tags"
    ]
    assert tags == {"a": "SKA", "b": "DLM", "c": "Hello", "d": "World"}


@pytest.mark.integration_test
def test_update_item_tags_exception(env):
    """Update the item_tags field of a data_item."""
    _ = env.ingest_requests.register_data_item(
        item_name="/my/ingest/test/item2", uri=TEST_URI, storage_name="MyDisk"
    )
    with pytest.raises(InvalidQueryParameters):
        data_item.update_item_tags(
            "/my/ingest/test/missing", item_tags={"a": "SKA", "b": "DLM", "c": "dummy"}
        )

    assert [] == env.data_item_requests.query_data_item(item_name="/my/ingest/test/missing")


@pytest.mark.integration_test
def test_expired_by_storage_daemon(env):
    """Test an expired data item is deleted by the storage manager."""
    fname = TEST_URI
    # test no expired items were found
    result = env.request_requests.query_expired()
    assert len(result) == 0

    # test no deleted items were found
    result = env.request_requests.query_deleted()
    assert len(result) == 0

    # add an item, and expire immediately
    uid = env.ingest_requests.register_data_item(item_name=fname, uri=fname, storage_name="MyDisk")
    data_item.set_state(uid=uid, state="READY")
    data_item.set_uid_expiration(uid, "2000-01-01")

    # check the expired item was found
    result = env.request_requests.query_expired()
    assert len(result) == 1

    # run storage daemon code
    # TODO: not a client endpoint
    # pylint: disable-next=import-outside-toplevel
    from ska_dlm.dlm_storage.dlm_storage_requests import delete_uids

    delete_uids()

    # check that the daemon deleted the item
    result = env.request_requests.query_deleted()
    assert result[0]["uid"] == uid


@pytest.mark.integration_test
def test_query_new(env):
    """Test for newly created data_items."""
    check_time = "2024-01-01"
    _ = env.ingest_requests.register_data_item(
        item_name="/my/ingest/test/item", uri=TEST_URI, storage_name="MyDisk"
    )
    result = env.request_requests.query_new(check_time)
    assert len(result) == 1


@pytest.mark.integration_test
def test_persist_new_data_items(env):
    """Test making new data items persistent."""
    check_time = "2024-01-01"
    _ = env.ingest_requests.register_data_item(
        item_name="/my/ingest/test/item", uri=TEST_URI, storage_name="MyDisk"
    )
    result = persist_new_data_items(check_time)
    # negative test, since there is only a single volume registered
    assert result == {"/my/ingest/test/item": False}

    # configure additional storage volume
    __initialise_storage_config(env)
    # and run again...
    result = persist_new_data_items(check_time)
    assert result == {"/my/ingest/test/item": True}


@pytest.mark.integration_test
def test_populate_metadata_col(env):
    """Test that the metadata is correctly saved to the metadata column."""
    # Register data item with metadata
    uid = env.ingest_requests.register_data_item(
        item_name="/my/metadata/test/item",  # item_name
        uri=TEST_URI,  # uri
        storage_name="MyDisk",  # storage_name
        metadata=METADATA_RECEIVED,  # metadata
    )

    metadata_str_from_db = env.data_item_requests.query_data_item(uid=uid)
    METADATA_RECEIVED["uid"] = uid
    METADATA_RECEIVED["item_name"] = "/my/metadata/test/item"
    assert metadata_str_from_db[0]["metadata"] == METADATA_RECEIVED

    metadata_dict_from_db = metadata_str_from_db[0]["metadata"]
    assert isinstance(metadata_dict_from_db, dict)  # otherwise the data might be double encoded

    assert isinstance(metadata_dict_from_db["execution_block"], str)


@pytest.mark.integration_test
def test_query_migration(env: DlmTestClient):
    """Test that query migration returns an empty set."""
    result = env.migration_requests.query_migrations()
    assert len(result) == 0
