# DP Cluster

Typical usage of the DLM:

1. Obtain an API token, authorizing use of the DLM by a specific user
2. Determine the location of the files you wish to add
3. Register that location with the DLM system. Note the location must be accessible (via rclone) from the DLM
4. Ingest the files into DLM one-by-one
5. Instruct DLM to migrate the newly ingested item to a secondary storage
6. Query the location of all copies of the item
7. Access the items via the [Data Product Dashboard](https://developer.skao.int/projects/ska-dataproduct-dashboard/en/latest/?badge=latest)

## Request API

### Step 1: Obtain an API token

To obtain an API token:

* Open a browser and go to the `/token_by_auth_flow` endpoint on the DLM server URL. For example: `https://sdhp.stfc.skao.int/dp-yanda/dlm/token_by_auth_flow`.
* Login with your SKAO credentials
* If successful, a token will be returned. Copy the token.

### Steps 2-6: ska-dlm REST API

The source code below demonstrates how to register a data item on the Acacia storage.
_Note that at the time of writing (07 Feb 2025), the restful endpoint tutorial only works by either:
(1) running this with VPN access or (2) running this from a terminal session inside the cluster using http://ska-dlm-gateway.dp-yanda.svc.cluster.local_

```python
from requests import Session

# this URL is for DLM deployment in the Yanda namespace on the DP integration cluster
# other known locations are shown below
DLM_URL = "https://sdhp.stfc.skao.int/dp-yanda/dlm"

# Prepare token to be placed in the header of any REST call
token = <your token>
bearer = {"Authorization": f"Bearer {token}"}

# create location details
location_name = "Pawsey"
location_type = "HPC centre"

# check if this location is already known to DLM
session = Session()
location = session.get(
    f"{DLM_URL}/storage/query_location", params={"location_name": location_name}, headers=bearer, timeout=60
)
print(location.json())
location_id = location.json()[0]["location_id"]  # if location exists
# if it doesn't already exist, initialise this location
loc_params = {
    "location_name": location_name,
    "location_type": location_type,
}
location = session.post(f"{DLM_URL}/storage/init_location", params=loc_params, headers=bearer, timeout=60)
print(location.json())
location_id = location.json()  # get the location id

# check if the 'Acacia' storage is already known to DLM
storage_params = {
    "storage_name": "Acacia",
    "location_id": location_id,
}
storage = session.get(f"{DLM_URL}/storage/query_storage", params=storage_params, headers=bearer, timeout=60)
print(storage.json())
storage_id = storage.json()[0]["storage_id"]  # if the storage exists
# if it doesn't already exist, initialise this storage
storage_params = {
    "storage_name": "Acacia",
    "location_id": location_id,
    "storage_type": "object store",
    "storage_interface": "s3",
    "storage_capacity": 100000000,
}
storage = session.post(
    f"{DLM_URL}/storage/init_storage", params=storage_params, headers=bearer, timeout=60
)
print(storage.json())
storage_id = storage.json()  # get the storage_id

# check if a storage config for this storage is already known to DLM
config = session.get(
    f"{DLM_URL}/storage/get_storage_config", params={"storage_id": storage_id}, headers=bearer, timeout=60
)
print(config.json())
# supply an rclone config for this storage (if it doesn’t already exist)
acacia_config = {
    "name": "Acacia",
    "type": "s3",
    "parameters": {
        "access_key_id": "<your-access-key-id>",
        "endpoint": "https://projects.pawsey.org.au",
        "provider": "Ceph",
        "secret_access_key": "<your-secret-access-key>",
    },
}
config = session.post(
    f"{DLM_URL}/storage/create_storage_config", params={"storage_id": storage_id},
    json=acacia_config,
    headers=bearer,
    timeout=60,
)
print(config.json())

# register a data item that exists on Acacia
item_params = {
    "item_name": "test_item",
    "uri": "rascil/1197634128-cal_avg32.ms.tar.xj",
    "storage_name": "Acacia",
    "storage_id": storage_id,
}
json_body = {"execution_block": "eb-m001-20191031-12345"}  # metadata
acacia_response = session.post(
    f"{DLM_URL}/ingest/register_data_item", params=item_params, json=json_body, headers=bearer, timeout=60
)
print(acacia_response.json())

# trigger a migration to a second storage
# initialise a destination storage (if it doesn't already exist), using the method above
migration_params = {"item_name": "test_item", "destination_name": <dest_storage>, "path": <dest_path>}
migration_response = session.post(
    f"{DLM_URL}/migration/copy_data_item", params=migration_params, headers=bearer, timeout=60
)
print(migration_response.json())

# query for all copies of the item
response = session.get(
    f"{DLM_URL}/request/query_data_item", params={"item_name": "test_item",}, headers=bearer, timeout=60,
)
print(response.json())
```

### Step 7: Access via Data Product Dashboard

At time of writing, here are the known medium-term deployments of the DLM system:

| Location                         | Data Lifecycle Management URL           | Data Product Dashboard URL                                                  |
| -------------------------------- | --------------------------------------- | --------------------------------------------------------------------------- |
| DP Integration (yanda namespace) | https://sdhp.stfc.skao.int/dp-yanda/dlm | https://sdhp.stfc.skao.int/integration-ska-dataproduct-dashboard/dashboard/ |
