"""Storage Manager Daemon."""

import logging
import os
import sys
from datetime import datetime
from time import sleep

from ska_dlm import dlm_migration, dlm_request, dlm_storage
from ska_dlm.exceptions import DataLifecycleError

from .. import CONFIG

logger = logging.getLogger(__name__)


def persist_new_data_items(last_check_time: str) -> dict:
    """Check for new data items (since the last query), if found, copy to a second location.

    Parameters:
    -----------
    last_check_time: ISO formatted datetime string

    Returns:
    --------
    dict, with entries of the form {item_name:status}
    """
    new_data_items = dlm_request.query_new(last_check_time)
    item_names = [n["item_name"] for n in new_data_items]
    stat = dict(zip(item_names, [False] * len(new_data_items)))

    storages = dlm_storage.query_storage()
    if not storages:
        logger.error("Could not find any storage volumes!")
        return stat
    for new_data_item in new_data_items:
        logger.info("Found new data item %s", new_data_item["item_name"])

        # TODO: check phase?

        new_storage = [s for s in storages if s["storage_id"] != new_data_item["storage_id"]]
        if new_storage == []:
            logger.error("Unable to identify a suitable new storage volume!")

            logger.info("Storage volumes found: %s", storages)
            continue
        new_storage = new_storage[0]
        dest_id = new_storage["storage_id"]
        try:
            dlm_migration.copy_data_item(uid=new_data_item["uid"], destination_id=dest_id)
        except DataLifecycleError:
            logger.exception("Copy of data_item %s unsuccessful!", new_data_item["item_name"])
        logger.info(
            "Persisted %s to volume %s", new_data_item["item_name"], new_storage["storage_name"]
        )
        stat[new_data_item["item_name"]] = True
    return stat


def main():
    """Begin a long-running process."""
    last_new_data_item_query_time = datetime.now().isoformat()

    while True:
        dlm_storage.delete_uids()
        persist_new_data_items(last_new_data_item_query_time)
        last_new_data_item_query_time = datetime.now().isoformat()
        # check_storage_capacity()
        # perform_phase_transitions()

        sleep(CONFIG.DLM.SLEEP_DURATION)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)