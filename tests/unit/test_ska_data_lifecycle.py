#!/usr/bin/env python

"""Tests for `ska_data_lifecycle` package."""
import logging
import os
from datetime import timedelta
from unittest import TestCase

import inflect
import pytest
import requests

from ska_dlm import CONFIG, data_item, dlm_ingest, dlm_request, dlm_storage

LOG = logging.getLogger("data-lifecycle-test")
LOG.setLevel(logging.DEBUG)


class TestDlm(TestCase):
    """
    Unit tests for the DLM.

    NOTE: Currently some of them are dependent on each other.
    """

    @pytest.fixture(scope="class", autouse=True)
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
        dlm_storage.create_storage_config(uuid, config='{"MyHost": {"type": "local"}}')
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
        uid = dlm_ingest.ingest_data_item("/my/ingest/test/item", "/LICSENSE", "MyDisk")
        assert len(uid) == 36

    def test_register_data_item(self):
        """Test the register_data_item function."""
        uid = dlm_ingest.register_data_item("/my/ingest/test/item", "/LICSENSE", "MyDisk")
        assert len(uid) == 0

    def test_query_expired_empty(self):
        """Test the query expired returning an empty set."""
        result = dlm_request.query_expired()
        success = len(result) == 0
        assert success

    def test_query_expired(self):
        """Test the query expired returning records."""
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
        uid = dlm_request.query_data_item(item_name="this/is/the/first/test/item")[0]["uid"]
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
        uid = dlm_ingest.ingest_data_item(fpath)
        uid = dlm_request.query_data_item(item_name=fpath)[0]["uid"]
        storage_id = dlm_storage.query_storage(storage_name="MyDisk")[0]["storage_id"]
        res = dlm_storage.delete_data_item_payload(uid)
        res = data_item.set_uri(uid, f"{fpath}", storage_id)
        res = data_item.set_state(uid, "DELETED")
        assert res
