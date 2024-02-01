"""Storage Manager Daemon."""

import logging
import os
import sys
from time import sleep

from ska_dlm import dlm_request, dlm_storage

SLEEP_DURATION = 2  # seconds

logger = logging.getLogger(__name__)


def expire_uids():
    """Check for expired data items and trigger deletion."""
    expired_data_items = dlm_request.query_expired()

    for uid in expired_data_items:
        dlm_storage.expire_data_item(uid)

    if len(expired_data_items) > 0:
        logger.info("Expired %s data items", {len(expired_data_items)})


def check_storage_capacity():
    """Check remaining capacity of all storage items."""
    capacity_limited_storage_items = dlm_storage.query_capacity_limited()

    for storage_item in capacity_limited_storage_items:
        logger.info("storage_item %s nearing full capacity", {storage_item})


def perform_phase_transitions():
    """Check for OIDs with insufficient phase, and trigger a phase transition."""
    required_phase_transitions = dlm_storage.query_phase_transitions()

    for oid in required_phase_transitions:
        logger.info("phase transition required for oid: %s", {oid})


def main():
    """Begin a long-running process."""
    while True:
        expire_uids()
        check_storage_capacity()
        perform_phase_transitions()

        sleep(SLEEP_DURATION)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)
