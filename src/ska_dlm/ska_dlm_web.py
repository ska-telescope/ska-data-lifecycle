"""Main module."""
from ska_dlm import dlm_request, dlm_storage
from flask import Flask, request
from prettytable import PrettyTable

app = Flask(__name__)

def _get_list(args):
    """List data items in one or more storage location(s)."""
    return dlm_request.query_data_item(item_name="")

@app.route('/oid/<oid>')
def get_locations(oid):
    # determine response type
    accept_header = request.headers.get('Accept')
    reply_with_html = "text/html" in accept_header
    print("accept_header", accept_header, "reply_with_html", reply_with_html)

    # build location map
    location_map = {}
    location_items = dlm_storage.query_location()
    for li in location_items:
        location_map[li['location_id']] = li
    
    # build storage map
    storage_map = {}
    storage_items = dlm_storage.query_storage()
    for si in storage_items:
        storage_map[si['storage_id']] = si

    data_items = dlm_request.query_data_item(oid=oid)

    if data_items is None:
        return "OID " + oid + " Not Found"

    x = PrettyTable()
    x.field_names = ["name", "storage", "location", "oid", "uid", "phase", "state", "expired", "deleted"]
    for di in data_items:
        storage = storage_map[di['storage_id']]
        location = location_map[storage['location_id']]

        x.add_row([di['item_name'], storage['storage_name'], location['location_name'], di['oid'], di['uid'], di['item_phase'], di['item_state'], di['expired'], di['deleted']])

    if reply_with_html:
        return "<!DOCTYPE html><html><head><script>setTimeout(function(){window.location.reload();}, 5000);</script></head><body>" + x.get_html_string() + "</body></html>"
    else:
        return x.get_formatted_string("json", header=False)

@app.route("/")
def base():
    return "<p>Hello, World!</p>"

