"""Main module."""
import argparse
import logging

import requests
from prettytable import PrettyTable

from ska_dlm import CONFIG, dlm_ingest, dlm_request

logger = logging.getLogger(__name__)

COMMAND_ADD = "add"
COMMAND_CLEAR = "clear"
COMMAND_LIST = "list"


def _add(args):
    """Add a data item."""
    logger.info(args.command)
    dlm_ingest.ingest_data_item(args.item_name, "/LICENSE", args.storage_name)


def _clear(args):
    """Clear the SKA DLM database."""
    logger.info(args.command)
    request_url = f"{CONFIG.REST.base_url}"
    requests.delete(f"{request_url}/storage_config", timeout=2)
    requests.delete(f"{request_url}/data_item", timeout=2)
    requests.delete(f"{request_url}/storage", timeout=2)
    requests.delete(f"{request_url}/location", timeout=2)


def _list(args):
    """List data items in one or more storage location(s)."""
    logger.info(args.command)
    table = PrettyTable()

    data_items = dlm_request.query_data_item(item_name="")
    table.field_names = ["Name", "oid", "uid", "Phase", "State", "Expired", "Deleted"]
    for data_item in data_items:
        table.add_row(
            [
                data_item["item_name"],
                data_item["oid"][0:8] + "...",
                data_item["uid"][0:8] + "...",
                data_item["item_phase"],
                data_item["item_state"],
                data_item["expired"],
                data_item["deleted"],
            ]
        )
    print(table)


def main():
    """Control the main execution of the program."""
    parser = argparse.ArgumentParser()
    parent_parser = argparse.ArgumentParser(add_help=False)
    # parent_parser.add_argument(
    #    "-n",
    #    "--notify-data-migration-manager",
    #    action="store_true",
    #    help="notify the data migration manager when a new data product metadata file is written",
    # )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # list
    parser_list_mode = subparsers.add_parser(
        COMMAND_LIST,
        parents=[parent_parser],
        help="list data items in one or more storage location(s)",
    )
    parser_list_mode.add_argument(
        "-o",
        "--output",
        default="output_file.txt",
        help="filename of the output metadata file",
    )

    # add
    parser_add_mode = subparsers.add_parser(
        COMMAND_ADD,
        parents=[parent_parser],
        help="add a data item to storage",
    )
    parser_add_mode.add_argument("--item_name", nargs="*", help="The file to add", required=True)
    parser_add_mode.add_argument(
        "--storage-name",
        nargs="*",
        help="The destination storage location for the file",
        required=True,
    )

    # clear
    subparsers.add_parser(
        COMMAND_CLEAR,
        parents=[parent_parser],
        help="clear the SKA DLM database",
    )

    commands = {
        COMMAND_ADD: _add,
        COMMAND_CLEAR: _clear,
        COMMAND_LIST: _list,
    }

    args = parser.parse_args()
    print(args.command)
    commands[args.command](args)


if __name__ == "__main__":
    main()
