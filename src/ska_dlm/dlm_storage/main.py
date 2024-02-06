"""Storage Manager Daemon."""

import logging
import os
import sys
from time import sleep

from ska_dlm import dlm_ingest, dlm_request, dlm_storage

SLEEP_DURATION = 2  # seconds
STORAGE_WARNING_PERCENTAGE = 80.0

logger = logging.getLogger(__name__)


def expire_uids():
    """Check for expired data items and trigger deletion."""
    expired_data_items = dlm_request.query_expired()

    for uid in expired_data_items:
        dlm_ingest.delete_data_item(uid=uid)

    if len(expired_data_items) > 0:
        logger.info("Expired %s data items", len(expired_data_items))


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
        check_storage_capacity()
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
