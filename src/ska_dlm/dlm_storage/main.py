"""Storage Manager Daemon."""

import logging
import os
import sys
from datetime import datetime
from time import sleep

from ska_dlm import dlm_migration, dlm_request, dlm_storage

SLEEP_DURATION = 2  # seconds
STORAGE_WARNING_PERCENTAGE = 80.0

logger = logging.getLogger(__name__)
last_new_data_item_query_time = ""


def update_last_new_item_query_time():
    """Update our record of the last time the database was queried for new items."""
    global last_new_data_item_query_time
    last_new_data_item_query_time = datetime.now().isoformat()


def expire_uids():
    """Check for expired data items and trigger deletion."""
    expired_data_items = dlm_request.query_expired()

    for uid in expired_data_items:
        success = dlm_storage.delete_data_item_payload(uid)

        if not success:
            logger.warning("Unable to delete data item payload: %s", uid)

    if len(expired_data_items) > 0:
        logger.info("Expired %s data items", len(expired_data_items))


def check_for_new_data_items():
    """Check for new data items (since the last query), if found, copy to a second location."""
    query = (
        "uid_creation=gt."
        + last_new_data_item_query_time
        + "&item_phase=eq.GAS&item_state=eq.READY&select=uid,item_name,uri"
    )
    new_data_items = dlm_request.query_data_item(query_string=query)
    update_last_new_item_query_time()

    for new_data_item in new_data_items:
        logger.info("Found new data item %s", new_data_item["item_name"])

        # TODO: check phase?

        # TODO: find a new location

        # make a copy
        dlm_migration.copy_data_item(uid=new_data_item["uid"])


def check_storage_capacity():
    """Check remaining capacity of all storage items."""
    storage_items = dlm_storage.query_storage(query_string="")

    for storage_item in storage_items:
        if storage_item["storage_use_pct"] >= STORAGE_WARNING_PERCENTAGE:
            logger.warning(
                "storage_item %s nearing full capacity (%s)",
                storage_item["storage_name"],
                storage_item["storage_use_pct"],
            )


def perform_phase_transitions():
    """Check for OIDs with insufficient phase, and trigger a phase transition."""
    required_phase_transitions = []  # dlm_storage.query_phase_transitions()

    for oid in required_phase_transitions:
        logger.warning("Incomplete implementation: phase transition required for oid: %s", oid)


def main():
    """Begin a long-running process."""
    while True:
        expire_uids()
        check_for_new_data_items()
        # check_storage_capacity()
        # perform_phase_transitions()

        sleep(SLEEP_DURATION)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)
