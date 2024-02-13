#!/usr/bin/env python

"""Tests for `ska_data_lifecycle` package."""
import logging
import os
from datetime import timedelta
from unittest import TestCase

import inflect
import pytest
import requests

from ska_dlm import CONFIG, data_item, dlm_ingest, dlm_migration, dlm_request, dlm_storage

LOG = logging.getLogger("data-lifecycle-test")
LOG.setLevel(logging.DEBUG)


class TestDlm(TestCase):
    """
    Unit tests for the DLM.

    NOTE: Currently some of them are dependent on each other.
    """

    @pytest.fixture(scope="function", autouse=True)
    def setup_and_teardown(self):
        """Initialze the tests."""
        # we need a location to register the storage
        location_id = dlm_storage.init_location("MyOwnStorage", "Server")
        uuid = dlm_storage.init_storage(
            storage_name="MyDisk",
            location_id=location_id,
            storage_type="disk",
            storage_interface="posix",
            storage_capacity=100000000,
        )
        config = '{"name":"MyDisk","type":"local", "parameters":{}}'
        dlm_storage.create_storage_config(uuid, config=config)
        # configure rclone
        dlm_storage.rclone_config(config)
        yield
        # Remove some records from the DB
        request_url = f"{CONFIG.REST.base_url}"
        requests.delete(f"{request_url}/storage_config", timeout=2)
        requests.delete(f"{request_url}/data_item", timeout=2)
        requests.delete(f"{request_url}/storage", timeout=2)
        requests.delete(f"{request_url}/location", timeout=2)

    def test_init(self):
        """Test data_item init."""
        engine = inflect.engine()
        success = True
        for i in range(1, 51, 1):
            ordinal = engine.number_to_words(engine.ordinal(i))
            uid = dlm_ingest.init_data_item(f"this/is/the/{ordinal}/test/item")
            if uid is None:
                success = False
        assert success

    def test_ingest_data_item(self):
        """Test the ingest_data_item function."""
        uid = dlm_ingest.ingest_data_item("/my/ingest/test/item", "/LICENSE", "MyDisk")
        assert len(uid) == 36

    def test_register_data_item(self):
        """Test the register_data_item function."""
        uid = dlm_ingest.register_data_item("/my/ingest/test/item2", "/LICENSE", "MyDisk")
        assert len(uid) == 36
        uid = dlm_ingest.register_data_item("/my/ingest/test/item2", "/LICENSE", "MyDisk")
        assert len(uid) == 0

    def test_query_expired_empty(self):
        """Test the query expired returning an empty set."""
        result = dlm_request.query_expired()
        success = len(result) == 0
        assert success

    def test_query_expired(self):
        """Test the query expired returning records."""
        self.test_init()
        offset = timedelta(days=1)
        result = dlm_request.query_expired(offset)
        success = len(result) != 0
        assert success

    def test_location_init(self):
        """Test initialisation on a location."""
        # This returns an empty string if unsuccessful
        fail = dlm_storage.init_location() == ""
        assert fail
        success = dlm_storage.init_location("TestLocation", "SKAO Data Centre") != ""
        assert success
        request_url = f"{CONFIG.REST.base_url}"
        requests.delete(f"{request_url}/location", timeout=2)

    def test_set_uri_state_phase(self):
        """Update a data_item record with the pointer to a file."""
        fname = "dlm_test_file_1.txt"
        with open(fname, "w", encoding="UTF-8") as tfile:
            tfile.write("Welcome to the great DLM world!")
        fpath = os.path.abspath("dlm_test_file.txt")
        fpath = fpath.replace(f"{os.environ['HOME']}/", "")
        uid = dlm_ingest.init_data_item(item_name="this/is/the/first/test/item")
        storage_id = dlm_storage.query_storage(storage_name="MyDisk")[0]["storage_id"]
        res = data_item.set_uri(uid, f"{fpath}", storage_id)
        assert res != ""
        res = data_item.set_state(uid, "READY")
        assert res != ""
        res = data_item.set_phase(uid, "PLASMA")
        assert res != ""
        os.unlink(fname)

    def test_delete_item_payload(self):
        """Delete the payload of a data_item."""
        fpath = "dlm_test_file_2.txt"
        with open(fpath, "w", encoding="UTF-8") as tfile:
            tfile.write("Welcome to the great DLM world!")
        storage_id = dlm_storage.query_storage(storage_name="MyDisk")[0]["storage_id"]
        uid = dlm_ingest.ingest_data_item(fpath)
        uid = dlm_request.query_data_item(item_name=fpath)[0]["uid"]
        assert dlm_storage.delete_data_item_payload(uid) is True
        res = data_item.set_uri(uid, f"{fpath}", storage_id)
        res = data_item.set_state(uid, "DELETED")
        assert res

    def test_storage_config(self):
        """Add a new location, storage and configuration to the rclone server."""
        location = dlm_storage.query_location("MyHost")
        if location:
            location_id = location[0]["location_id"]
        else:
            location_id = dlm_storage.init_location("MyHost", "Server")
        assert len(location_id) == 36
        config = '{"name":"MyDisk2","type":"local", "parameters":{}}'
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
        assert dlm_storage.rclone_config(config) is True

    def test_copy(self):
        """Copy a test file from one storage to another."""
        self.test_storage_config()
        dest_id = dlm_storage.query_storage("MyDisk2")[0]["storage_id"]
        uid = dlm_ingest.register_data_item("/my/ingest/test/item2", "/LICENSE", "MyDisk")
        assert len(uid) == 36
        assert (
            dlm_migration.copy_data_item(uid=uid, destination_id=dest_id, path="LICENSE_copy")
            is True
        )
        os.unlink("LICENSE_copy")

    def test_expired_by_storage_daemon(self):
        """Test an expired data item is deleted by the storage manager."""
        # test no expired items were found
        result = dlm_request.query_expired()
        assert len(result) == 0

        # test no deleted items were found
        result = dlm_request.query_deleted()
        assert len(result) == 0

        # add an item, and expire immediately
        uid = dlm_ingest.ingest_data_item(item_name="/dlm_test_file.txt", storage_name="MyDisk")
        data_item.set_uid_expiration(uid, "2000-01-01T00:00:01.000000")

        # run storage daemon code
        from ska_dlm.dlm_storage.main import delete_uids

        delete_uids()

        # check the expired item was found
        result = dlm_request.query_expired()
        assert len(result) == 1

        # check that the daemon deleted the item
        result = dlm_request.query_deleted()
        assert len(result) == 1
