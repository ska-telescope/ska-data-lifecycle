#!/usr/bin/env python

"""Unit tests for dlm_storage."""


import pytest

from ska_dlm import dlm_storage
from ska_dlm.exceptions import InvalidQueryParameters


def test_location_init():
    """Test initialisation on a location."""
    # Successful initialisation
    dlm_storage.init_location("TestLocation1", "low-integration")
    location = dlm_storage.query_location(location_name="TestLocation1")[0]
    assert location["location_type"] == "low-integration"

    # Unsuccessful initialisations
    with pytest.raises(InvalidQueryParameters):
        dlm_storage.init_location(location_name="TestLocation2", location_type="")

    with pytest.raises(InvalidQueryParameters):
        dlm_storage.init_location(location_name="", location_type="low-integration")


def test_initialise_storage_config():
    """Add a new location, storage and configuration to the rclone server."""
    location = dlm_storage.query_location("MyHost")
    if location:
        location_id = location[0]["location_id"]
    else:
        location_id = dlm_storage.init_location("MyHost", "low-integration")
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


def test_invalid_storage_type():
    """Test that an invalid storage_type raises a ValueError."""
    location_id = dlm_storage.init_location("MyHostInvalid", "low-integration")

    with pytest.raises(ValueError) as exc_info:
        dlm_storage.init_storage(
            storage_name="MyDiskInvalid",
            location_id=location_id,
            root_directory="/data/",
            storage_type="disk",  # Invalid enum
            storage_interface="posix",
            storage_capacity=100000000,
        )
    assert "Invalid storage type disk" in str(exc_info.value)
    assert "filesystem" in str(exc_info.value)
