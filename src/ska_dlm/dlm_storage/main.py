"""Storage Manager Daemon."""

import logging
import signal
from datetime import datetime, timezone

import ska_ser_logging

from ska_dlm import data_item, dlm_migration, dlm_request, dlm_storage
from ska_dlm.exceptions import DataLifecycleError

from .. import CONFIG

logger = logging.getLogger(__name__)


def persist_new_data_items(last_check_time: str) -> dict:
    """Check for new data items (since the last query), if found, copy to a second location.

    Parameters
    ----------
    last_check_time
        ISO formatted datetime string

    Returns
    -------
    dict
        dict with entries of the form {item_name:status}
    """
    new_data_items = dlm_request.query_new(last_check_time)
    if not new_data_items:
        logger.info("No new data items found.")
    item_names = [n["item_name"] for n in new_data_items]
    stat = dict(zip(item_names, [False] * len(new_data_items)))

    storages = dlm_storage.query_storage()
    if not storages:
        logger.error("Could not find any storage volumes!")
        return stat
    for new_data_item in new_data_items:
        logger.info("Found new data item %s", new_data_item["item_name"])

        # TODO: check phase?

        # Check if the data item has a storage_id
        if "storage_id" not in new_data_item or not new_data_item["storage_id"]:
            logger.warning("Data item %s has no storage_id", new_data_item["item_name"])
            # Use the first available storage
            if storages:
                new_storage = [storages[0]]
            else:
                logger.error("No storage volumes available!")
                continue
        else:
            # Filter out the current storage to find a different one
            new_storage = [s for s in storages if s["storage_id"] != new_data_item["storage_id"]]
            if not new_storage:
                logger.error("Unable to identify a suitable new storage volume!")
                logger.info("Current storage_id: %s", new_data_item["storage_id"])
                logger.info("Storage volumes found: %s", storages)
                continue
        new_storage = new_storage[0]
        dest_id = new_storage["storage_id"]
        copy_uid = None
        try:
            copy_uid = dlm_migration.copy_data_item(
                uid=new_data_item["uid"],
                destination_id=dest_id,
            )
            logger.info(
                "Persisted %s to volume %s",
                new_data_item["item_name"],
                new_storage["storage_name"],
            )
            data_item.set_phase(uid=new_data_item["uid"], phase="LIQUID")
            data_item.set_phase(uid=copy_uid["uid"], phase="LIQUID")
            stat[new_data_item["item_name"]] = True
        except DataLifecycleError:
            logger.exception("Copy of data_item %s unsuccessful!", new_data_item["item_name"])
    return stat


def main():
    """Begin a long-running process."""
    # We use signal.pause() at the end of the main loop to continue with the next
    # iteration. A SIGARLM is scheduled before that, and indicates that the loop
    # should continue, while SIGINT/SIGTERM will indicate that the program needs
    # to exit
    run_main_loop = True

    def handle_signal(signo, _frame):
        nonlocal run_main_loop
        if signo in (signal.SIGINT, signal.SIGTERM):
            logger.info("Received %s, ending program now", signal.Signals(signo).name)
            run_main_loop = False
            return
        assert signo == signal.SIGALRM

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGALRM, handle_signal)

    ska_ser_logging.configure_logging(level=logging.INFO)
    last_new_data_item_query_time = "2024-01-01"
    while run_main_loop:
        logger.info(
            "Running new/expired checks with timestamp: %s UTC",
            last_new_data_item_query_time,
        )
        dlm_storage.delete_uids()
        _ = persist_new_data_items(last_new_data_item_query_time)
        # check_storage_capacity()
        # perform_phase_transitions()

        last_new_data_item_query_time = datetime.now(timezone.utc).isoformat()[:19]
        signal.alarm(CONFIG.DLM.storage_manager.polling_interval)
        signal.pause()


if __name__ == "__main__":
    main()
