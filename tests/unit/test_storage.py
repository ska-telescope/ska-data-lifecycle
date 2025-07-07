#!/usr/bin/env python

"""Unit tests for dlm_storage."""


import pytest

from ska_dlm import dlm_storage
from ska_dlm.exceptions import InvalidQueryParameters


def test_location_init():
    """Test initialisation on a location."""
    # This returns an empty string if unsuccessful
    with pytest.raises(InvalidQueryParameters):
        dlm_storage.init_location(location_name="name", location_type="")
    with pytest.raises(InvalidQueryParameters):
        dlm_storage.init_location(location_name="", location_type="type")

    dlm_storage.init_location("TestLocation", "low-itf")
    location = dlm_storage.query_location(location_name="TestLocation")[0]
    assert location["location_type"] == "low-itf"


def test_initialise_storage_config():
    """Add a new location, storage and configuration to the rclone server."""
    location = dlm_storage.query_location("MyHost")
    if location:
        location_id = location[0]["location_id"]
    else:
        location_id = dlm_storage.init_location("MyHost", "external")
    assert len(location_id) == 36
    config = {"name": "MyDisk2", "type": "local", "parameters": {}}
    uuid = dlm_storage.init_storage(
        storage_name="MyDisk2",
        location_id=location_id,
        root_directory="/data/MyDisk2/",
        storage_type="filesystem",
        storage_interface="posix",
        storage_capacity=100000000,
    )
    assert len(uuid) == 36
    config_id = dlm_storage.create_storage_config(storage_id=uuid, config=config)
    assert len(config_id) == 36
    # configure rclone
    assert dlm_storage.create_rclone_config(config) is True
