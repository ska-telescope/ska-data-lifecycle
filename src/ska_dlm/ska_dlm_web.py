"""Main module."""
from flask import Flask, request
from prettytable import PrettyTable

from ska_dlm import dlm_request, dlm_storage

app = Flask(__name__)


@app.route("/oid/<oid>")
def get_locations(oid):
    """Reply with all the data items matching the given oid."""
    # determine response type
    accept_header = request.headers.get("Accept")
    reply_with_html = "text/html" in accept_header

    # build location map
    location_map = {}
    location_items = dlm_storage.query_location()
    for location_item in location_items:
        location_map[location_item["location_id"]] = location_item

    # build storage map
    storage_map = {}
    storage_items = dlm_storage.query_storage()
    for storage_item in storage_items:
        storage_map[storage_item["storage_id"]] = storage_item

    data_items = dlm_request.query_data_item(oid=oid)

    if data_items is None:
        return "OID " + oid + " Not Found"

    table = PrettyTable()
    table.field_names = [
        "name",
        "storage",
        "location",
        "oid",
        "uid",
        "phase",
        "state",
        "expired",
        "deleted",
    ]
    for data_item in data_items:
        storage = storage_map[data_item["storage_id"]]
        location = location_map[storage["location_id"]]

        table.add_row(
            [
                data_item["item_name"],
                storage["storage_name"],
                location["location_name"],
                data_item["oid"],
                data_item["uid"],
                data_item["item_phase"],
                data_item["item_state"],
                data_item["expired"],
                data_item["deleted"],
            ]
        )

    if reply_with_html:
        auto_reload_script = "setTimeout(function(){window.location.reload();}, 5000);"

        return (
            "<!DOCTYPE html><html><head><script>"
            + auto_reload_script
            + "</script></head><body>"
            + table.get_html_string()
            + "</body></html>"
        )

    return table.get_formatted_string("json", header=False)


@app.route("/")
def base():
    """Landing page view."""
    return "<p>Hello, World!</p>"
