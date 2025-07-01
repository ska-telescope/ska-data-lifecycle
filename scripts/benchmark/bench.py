"""Benchmark utility."""

import json
import logging
import time
from functools import partial
from multiprocessing.pool import ThreadPool
from typing import Callable

import yaml

from ska_dlm.exceptions import ValueAlreadyInDB
from tests.integration.client import (
    data_item_client,
    dlm_ingest_client,
    dlm_migration_client,
    dlm_storage_client,
)

logger = logging.getLogger(__name__)


def load_yaml(name: str) -> dict:
    """Open yaml config file."""
    with open(name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_clients(url: str, token: str):
    """Set client gateway URL and token."""
    dlm_storage_client.STORAGE_URL = url
    dlm_ingest_client.INGEST_URL = url
    dlm_migration_client.MIGRATION_URL = url
    data_item_client.REQUEST_URL = url
    dlm_storage_client.TOKEN = token
    dlm_ingest_client.TOKEN = token
    dlm_migration_client.TOKEN = token
    data_item_client.TOKEN = token


def setup_storage(storage: dict):
    """Setup defined storage."""
    store = dlm_storage_client.query_storage(storage["name"])
    if not store:
        location = dlm_storage_client.query_location(location_name=storage["location"])
        if not location:
            dlm_storage_client.init_location(
                location_name=storage["location"], location_type=storage["type"]
            )

        store = dlm_storage_client.init_storage(
            storage_name=storage["name"],
            location_name=storage["location"],
            storage_interface=storage["interface"],
            root_directory=storage["root_directory"],
            storage_type=storage["type"],
        )
    else:
        store = store[0]["storage_id"]

    store_config = dlm_storage_client.get_storage_config(storage_id=store)
    if not store_config:
        dlm_storage_client.create_storage_config(storage_id=store, config=storage["config"])

    dlm_storage_client.create_rclone_config(config=storage["config"])


def register_item(migration: dict):
    """Register data item."""
    try:
        dlm_ingest_client.register_data_item(
            item_name=migration["name"],
            uri=migration["uri"],
            item_type=migration["type"],
            storage_name=migration["source_storage"],
        )
    except ValueAlreadyInDB as e:
        logging.warning(str(e))


def get_data_item(oid: str, storage_id: str) -> list[dict]:
    """Get the details of a specific data item."""
    return data_item_client.query_data_item(oid=oid, storage_id=storage_id)


def copy_item(migration: dict) -> dict:
    """Copy item request to migration service."""
    return dlm_migration_client.copy_data_item(
        item_name=migration["name"],
        destination_name=migration["destination_storage"],
        path=migration["destination_path"],
    )


def get_record(migration_id: int) -> list:
    """Get migration record based on id."""
    return dlm_migration_client.get_migration_record(migration_id)[0]


def wait_for_migration(
    migration_tuple: tuple, migration_polltime: int, migration_callback: Callable[[dict], None]
) -> dict:
    """Wait for migration to finish."""
    name, m_id = migration_tuple
    while True:
        record = get_record(m_id)
        status = record["job_status"]
        if status:
            if status["finished"] is True:
                break
        time.sleep(migration_polltime)

    if migration_callback:
        migration_callback(record)

    return {name: record}


def run_bench(
    bench_config: dict,
    output_file_path: str,
    migration_polltime: int,
    migration_callback: Callable[[dict], None] = None,
):
    """Run data item migration performance benchmark."""
    logger.info("Setting up storage endpoints")

    for storage in bench_config["storage"]:
        setup_storage(bench_config["storage"][storage])

    migration_ids = []
    for migrate in bench_config["benchmarks"]:
        if bench_config["benchmarks"][migrate]["enabled"] is False:
            continue
        logger.info(f"Executing migration {migrate}")
        register_item(bench_config["benchmarks"][migrate])
        migration = copy_item(bench_config["benchmarks"][migrate])
        migration_ids.append((migrate, migration["migration_id"]))

    with ThreadPool() as pool:
        # issue tasks into the thread pool
        wait_for_migration_partial = partial(
            wait_for_migration,
            migration_polltime=migration_polltime,
            migration_callback=migration_callback,
        )
        result = pool.map_async(wait_for_migration_partial, migration_ids)
        logger.info("Waiting for migrations to finish")
        # wait for tasks to complete
        result.wait()
        results = result.get()

    logger.info("Migrations finished")

    if output_file_path:
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        logger.info(f"Output file generated: {output_file_path}")
    else:
        print(json.dumps(results, indent=4))
