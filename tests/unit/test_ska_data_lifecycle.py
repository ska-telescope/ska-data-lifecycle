#!/usr/bin/env python

"""Tests for `ska_data_lifecycle` package."""
import logging
import os
from datetime import timedelta
from unittest import TestCase

import inflect  # pylint disable E0401
import pytest

from ska_dlm import dlm_ingest, dlm_request, dlm_storage  # pylint disable E0401

LOG = logging.getLogger("data-lifecycle-test")
LOG.setLevel(logging.DEBUG)


class TestDlm(TestCase):
    """
    Unit tests for the DLM.

    NOTE: Currently some of them are dependent on each other.
    """

    def test_ingest(self):
        """Test data_item init."""
        engine = inflect.engine()
        success = True
        for i in range(1, 51, 1):
            ordinal = engine.number_to_words(engine.ordinal(i))
            uid = dlm_ingest.init_data_item(f"this/is/the/{ordinal}/test/item")
            if uid is None:
                success = False
        assert success

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

    def test_storage_init(self):
        """Test initialisation on a storage."""
        # Without required parameters
        fail = dlm_storage.init_storage() == ""
        assert fail
        # we need a location to register the storage
        location_id = dlm_storage.init_location("MyOwnStorage", "Server")
        uuid = dlm_storage.init_storage(
            storage_name="MyDisk",
            location_id=location_id,
            storage_type="disk",
            storage_interface="posix",
            storage_capacity=100000000,
        )
        success = len(uuid) == 36
        assert success

    @pytest.mark.skip(reason="Dependency issues. To be fixed in next merge")
    def test_set_uri_and_state(self):
        """Update a data_item record with the pointer to a file."""
        with open("dlm_test_file.txt", "w", encoding="UTF-8") as tfile:
            tfile.write("Welcome to the great DLM world!")
        fpath = os.path.abspath("dlm_test_file.txt")
        fpath = fpath.replace(f"{os.environ['HOME']}/", "")
        uid = dlm_request.query_data_item(item_name="this/is/the/first/test/item")[0]["uid"]
        storage_id = dlm_storage.query_storage(storage_name="MyDisk")[0]["storage_id"]
        res = dlm_ingest.set_uri(uid, f"{fpath}", storage_id)
        assert res != ""
        res = dlm_ingest.set_state(uid, "READY")
        assert res != ""
