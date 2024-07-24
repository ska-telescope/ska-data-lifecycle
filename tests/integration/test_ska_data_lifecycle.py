#!/usr/bin/env python

"""Tests for `ska_data_lifecycle` package."""

import datetime
import importlib
import json

import inflect
import pytest
import ska_sdp_metadata_generator as metagen
from requests_mock import Mocker

import tests.integration.client.dlm_ingest_client as dlm_ingest
import tests.integration.client.dlm_request_client as dlm_request
import tests.integration.client.dlm_storage_client as dlm_storage
from ska_dlm import CONFIG, data_item, dlm_migration
from ska_dlm.dlm_db.db_access import DB
from ska_dlm.dlm_ingest import notify_data_dashboard, register_data_item
from ska_dlm.dlm_storage import delete_data_item_payload, delete_uids, rclone_config
from ska_dlm.dlm_storage.main import persist_new_data_items
from ska_dlm.exceptions import InvalidQueryParameters, ValueAlreadyInDB
from tests.integration.client.dlm_gateway_client import get_token

ROOT = "/data/"
RCLONE_TEST_FILE_PATH = "/data/testfile"
"""A file that is available locally in the rclone container"""
RCLONE_TEST_FILE_CONTENT = "license content"
TODAY_DATE = datetime.datetime.now().strftime("%Y%m%d")
METADATA_RECEIVED = {
    "execution_block": "eb-meta-20240723-00000",
}


def _clear_database():
    DB.delete(CONFIG.DLM.dlm_table)
    DB.delete(CONFIG.DLM.storage_config_table)
    DB.delete(CONFIG.DLM.storage_table)
    DB.delete(CONFIG.DLM.location_table)


@pytest.fixture(name="auth", scope="session")
def auth_fixture(request):
    """Fixture for auth commandline param."""
    return bool(int(request.config.getoption("--auth")))


@pytest.fixture(name="env", scope="session")
def import_test_env_module(request):
    """Dynamically import module based on testing environment."""
    match request.config.getoption("--env"):
        case "k8s":
            env_module_name = "tests.common_k8s"
        case "local":
            env_module_name = "tests.common_local"
        case "docker":
            env_module_name = "tests.common_docker"
        case _:
            raise ValueError("unknown test configuration")

    mod = importlib.import_module(env_module_name)
    client_urls = mod.get_service_urls()

    # TODO: should not be reassigning global constants
    dlm_storage.STORAGE_URL = client_urls["dlm_storage"]
    dlm_ingest.INGEST_URL = client_urls["dlm_ingest"]
    dlm_request.REQUEST_URL = client_urls["dlm_request"]
    return mod


@pytest.fixture(scope="session", autouse=True)
def setup_auth(env, auth):
    """Initialze Auth per session."""
    # this should only run once per test suite
    if auth is True:
        token = get_token("admin", "admin", env.get_service_urls()["dlm_gateway"])
        dlm_request.REQUEST_BEARER = token
        dlm_ingest.INGEST_BEARER = token
        dlm_storage.STORAGE_BEARER = token


@pytest.fixture(scope="function", autouse=True)
def setup(env):
    """Initialze the tests."""
    _clear_database()

    env.write_rclone_file_content(RCLONE_TEST_FILE_PATH, RCLONE_TEST_FILE_CONTENT)

    # we need a location to register the storage
    location_id = dlm_storage.init_location("MyOwnStorage", "Server")
    uuid = dlm_storage.init_storage(
        storage_name="MyDisk",
        location_id=location_id,
        storage_type="disk",
        storage_interface="posix",
        storage_capacity=100000000,
    )
    config = {"name": "MyDisk", "type": "alias", "parameters": {"remote": "/"}}
    config = json.dumps(config)
    dlm_storage.create_storage_config(uuid, config=config)
    # configure rclone
    rclone_config(config)
    yield
    _clear_database()
    env.clear_rclone_data(ROOT)


def __initialize_data_item():
    """Test data_item init."""
    engine = inflect.engine()
    success = True
    for i in range(1, 51, 1):
        ordinal = engine.number_to_words(engine.ordinal(i))
        uid = dlm_ingest.init_data_item(f"this/is/the/{ordinal}/test/item")
        if uid is None:
            success = False
    assert success


@pytest.mark.skip(reason="Placeholder. We removed the ingest_data_item alias.")
def test_ingest_data_item():
    """Test the ingest_data_item function."""
    uid = register_data_item(
        "/my/ingest/test/item", RCLONE_TEST_FILE_PATH, "MyDisk", metadata=None
    )
    assert len(uid) == 36


def test_register_data_item_with_metadata():
    """Test the register_data_item function with provided metadata."""
    # pylint: disable-next=no-member
    uid = register_data_item(
        "/my/ingest/test/item2",
        RCLONE_TEST_FILE_PATH,
        "MyDisk",
        metadata=json.dumps(METADATA_RECEIVED),
    )
    assert len(uid) == 36
    with pytest.raises(ValueAlreadyInDB, match="Item is already registered"):
        # pylint: disable-next=no-member
        register_data_item(
            "/my/ingest/test/item2",
            RCLONE_TEST_FILE_PATH,
            "MyDisk",
            metadata=json.dumps(METADATA_RECEIVED),
        )


def test_query_expired_empty():
    """Test the query expired returning an empty set."""
    result = dlm_request.query_expired()
    success = len(result) == 0
    assert success


def test_query_expired():
    """Test the query expired returning records."""
    __initialize_data_item()
    uid = dlm_request.query_data_item()[0]["uid"]
    offset = datetime.timedelta(days=1)
    data_item.set_state(uid=uid, state="READY")
    result = dlm_request.query_expired(offset)
    success = len(result) != 0
    assert success


def test_location_init():
    """Test initialisation on a location."""
    # This returns an empty string if unsuccessful
    with pytest.raises(InvalidQueryParameters):
        dlm_storage.init_location()
    dlm_storage.init_location("TestLocation", "SKAO Data Centre")
    location = dlm_storage.query_location(location_name="TestLocation")[0]
    assert location["location_type"] == "SKAO Data Centre"


def test_set_uri_state_phase():
    """Update a data_item record with the pointer to a file."""
    uid = dlm_ingest.init_data_item(item_name="this/is/the/first/test/item")
    storage_id = dlm_storage.query_storage(storage_name="MyDisk")[0]["storage_id"]
    data_item.set_uri(uid, RCLONE_TEST_FILE_PATH, storage_id)
    assert dlm_request.query_data_item(uid=uid)[0]["uri"] == RCLONE_TEST_FILE_PATH
    data_item.set_state(uid, "READY")
    data_item.set_phase(uid, "PLASMA")
    items = dlm_request.query_data_item(uid=uid)
    assert len(items) == 1
    assert items[0]["item_state"] == "READY"
    assert items[0]["item_phase"] == "PLASMA"


# TODO: We don't want RCLONE_TEST_FILE_PATH to disappear after one test run.
def test_delete_item_payload():
    """Delete the payload of a data_item."""
    fpath = RCLONE_TEST_FILE_PATH
    storage_id = dlm_storage.query_storage(storage_name="MyDisk")[0]["storage_id"]
    uid = register_data_item(fpath, fpath, "MyDisk")
    data_item.set_state(uid, "READY")
    data_item.set_uri(uid, fpath, storage_id)
    queried_uid = dlm_request.query_data_item(item_name=fpath)[0]["uid"]
    assert uid == queried_uid
    delete_data_item_payload(uid)
    assert dlm_request.query_data_item(item_name=fpath)[0]["uri"] == fpath
    assert dlm_request.query_data_item(item_name=fpath)[0]["item_state"] == "DELETED"


def __initialize_storage_config():
    """Add a new location, storage and configuration to the rclone server."""
    location = dlm_storage.query_location("MyHost")
    if location:
        location_id = location[0]["location_id"]
    else:
        location_id = dlm_storage.init_location("MyHost", "Server")
    assert len(location_id) == 36
    config = {"name": "MyDisk2", "type": "alias", "parameters": {"remote": "/"}}
    config = json.dumps(config)
    uuid = dlm_storage.init_storage(
        storage_name="MyDisk2",
        location_id=location_id,
        storage_type="disk",
        storage_interface="posix",
        storage_capacity=100000000,
    )
    assert len(uuid) == 36
    config_id = dlm_storage.create_storage_config(uuid, config=config)
    assert len(config_id) == 36
    # configure rclone
    assert rclone_config(config) is True


def test_copy(env):
    """Copy a test file from one storage to another."""
    __initialize_storage_config()
    dest_id = dlm_storage.query_storage("MyDisk2")[0]["storage_id"]
    uid = register_data_item("/my/ingest/test/item2", RCLONE_TEST_FILE_PATH, "MyDisk")
    assert len(uid) == 36
    dest = "/data/testfile_copy"
    dlm_migration.copy_data_item(uid=uid, destination_id=dest_id, path=dest)
    assert RCLONE_TEST_FILE_CONTENT == env.get_rclone_local_file_content(dest)


def test_update_item_tags():
    """Update the item_tags field of a data_item."""
    _ = register_data_item("/my/ingest/test/item2", RCLONE_TEST_FILE_PATH, "MyDisk")
    res = data_item.update_item_tags(
        "/my/ingest/test/item2", item_tags={"a": "SKA", "b": "DLM", "c": "dummy"}
    )
    assert res is True
    res = data_item.update_item_tags(
        "/my/ingest/test/item2", item_tags={"c": "Hello", "d": "World"}
    )
    assert res is True
    tags = dlm_request.query_data_item(item_name="/my/ingest/test/item2")[0]["item_tags"]
    assert tags == {"a": "SKA", "b": "DLM", "c": "Hello", "d": "World"}


def test_expired_by_storage_daemon():
    """Test an expired data item is deleted by the storage manager."""
    fname = RCLONE_TEST_FILE_PATH
    # test no expired items were found
    result = dlm_request.query_expired()
    assert len(result) == 0

    # test no deleted items were found
    result = dlm_request.query_deleted()
    assert len(result) == 0

    # add an item, and expire immediately
    uid = register_data_item(item_name=fname, uri=fname, storage_name="MyDisk")
    data_item.set_state(uid=uid, state="READY")
    data_item.set_uid_expiration(uid, "2000-01-01")

    # check the expired item was found
    result = dlm_request.query_expired()
    assert len(result) == 1

    # run storage daemon code
    delete_uids()

    # check that the daemon deleted the item
    result = dlm_request.query_deleted()
    assert result[0]["uid"] == uid


def test_query_new():
    """Test for newly created data_items."""
    check_time = "2024-01-01"
    _ = register_data_item("/my/ingest/test/item", RCLONE_TEST_FILE_PATH, "MyDisk")
    result = dlm_request.query_new(check_time)
    assert len(result) == 1


def test_persist_new_data_items():
    """Test making new data items persistent."""
    check_time = "2024-01-01"
    _ = register_data_item("/my/ingest/test/item", RCLONE_TEST_FILE_PATH, "MyDisk")
    result = persist_new_data_items(check_time)
    # negative test, since there is only a single volume registered
    assert result == {"/my/ingest/test/item": False}

    # configure additional storage volume
    __initialize_storage_config()
    # and run again...
    result = persist_new_data_items(check_time)
    assert result == {"/my/ingest/test/item": True}


@pytest.mark.skip(reason="Will update soon")
def test_notify_data_dashboard():
    """Test that the write hook will post metadata file info to a URL."""
    # mock a response for this URL, a copy of the normal response from ska-sdp-dataproduct-api
    req_mock = Mocker()
    req_mock.post(
        CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata",
        text="New data product metadata file loaded and store index updated",
    )

    notify_data_dashboard({})


def test_populate_metadata_col():
    """Test that the metadata is correctly saved to the metadata column."""
    META_FILE = "/tmp/testfile"  # pylint: disable=invalid-name
    with open(META_FILE, "wt", encoding="ascii") as file:
        file.write(RCLONE_TEST_FILE_CONTENT)

    # Generate metadata
    metadata_object = metagen.generate_metadata_from_generator(META_FILE)
    metadata_json = metadata_object.get_data().to_json()  # MetaData obj -> benedict -> json str
    assert isinstance(metadata_json, str)
    try:
        json.loads(metadata_json)
    except json.JSONDecodeError as err:
        assert False, "Failed to decode JSON: %s. Check type." % err

    # Register data item
    uid = register_data_item(
        "/my/metadata/test/item", RCLONE_TEST_FILE_PATH, "MyDisk", metadata=metadata_json
    )

    metadata_str_from_db = dlm_request.query_data_item(uid=uid)
    assert isinstance(metadata_str_from_db[0]["metadata"], str)

    metadata_dict_from_db = json.loads(metadata_str_from_db[0]["metadata"])
    assert isinstance(metadata_dict_from_db, dict)  # otherwise the data might be double encoded

    assert metadata_dict_from_db["interface"] == "http://schema.skao.int/ska-data-product-meta/0.1"
    assert metadata_dict_from_db["execution_block"].startswith(f"eb-meta-{TODAY_DATE}")

    assert metadata_dict_from_db["context"] == {}
    assert "config" in metadata_dict_from_db  # All the fields in here are None atm
    assert metadata_dict_from_db["files"] == [
        {
            "crc": "62acf8ce",
            "description": "",
            "path": "testfile",
            "size": 15,
            "status": "done",
        }
    ]
    assert metadata_dict_from_db["obscore"] == {
        "dataproduct_type": "Unknown",
        "obs_collection": "Unknown",
        "access_format": "application/unknown",
        "facility_name": "SKA-Observatory",
        "instrument_name": "Unknown",
        "access_estsize": 0,
    }
