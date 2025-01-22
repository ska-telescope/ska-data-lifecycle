
# Example Usage

Typical usage of the DLM:

1. Obtain an API token, authorizing use of the DLM by a specific user
2. Determine the location of the files you wish to add
3. Register that location with the DLM system. Note the location must be accessible (via rclone) from the DLM
4. Ingest the files into DLM one-by-one
5. Instruct DLM to migrate the newly ingested item to a secondary storage
6. Query the location of all copies of the item
7. Access the items via the ska-dataproduct-dashboard

## Step 1: Obtain an API token

To obtain an API token:

* Open a browser and go to the `/token_by_auth_flow` endpoint on the DLM server URL. For example: `https://sdhp.stfc.skao.int/dp-yanda/dlm/token_by_auth_flow`.
* Login with your SKAO credentials
* If successful, a token will be returned. Copy the token.

## Steps 2-6: Data Lifecycle Management

Once a token is ready, interactions with DLM can be done in two ways:

1. ska-dlm-client - a standalone DLM client that can be configured to automatically ingest data items
2. manually, using either the ska-dlm REST API, python methods or CLI interface.

## ska-dlm-client

The ska-dlm-client is the recommended way of using the DLM. Once configured, the ska-dlm-client will trigger on creation of a new file, or on reception of a kafka message, automatically ingesting the specified item into the DLM.

For more complete information, refer to the ska-dlm-client [repository](https://gitlab.com/ska-telescope/ska-dlm-client/) and [readthedocs](https://ska-telescope-ska-dlm-client.readthedocs.io/en/latest/).

## ska-dlm REST API

Interaction with the DLM is also possible via the REST API. The source code below is a typical example.
Don't forget to spin-up the DLM services first (e.g., by running `make python-pre-test` from within your DLM directory).

```python
from requests import Session

# this URL is for DLM deployment in the Yanda namespace on the DP integration cluster
# other known locations are shown below
DLM_URL = "https://sdhp.stfc.skao.int/dp-yanda/dlm"

# Prepare token to be placed in the header of any REST call
bearer = {"Authorization": f"Bearer {your token}"}

# create details for this location
location_name="ThisLocationName"
location_type="ThisLocationType"

# check if the location 'ThisLocationName' is already known to DLM
session = Session()
location = session.get(f"{DLM_URL}/storage/query_location", params={"location_name": location_name}, headers=bearer, timeout=60)
print(location.json())
# initialise this location (if it doesn't already exist)
params = {
  "location_name": location_name,
  "location_type": location_type,
}
location = session.post(f"{DLM_URL}/storage/init_location", params=params, headers=bearer, timeout=60)
print(location.json())
# get the location id
location_id = location.json()[0]["location_id"]

# check if the storage 'MyDisk' is already known to DLM
params_loc = {
  "storage_name": "MyDisk",
  "location_id": location_id,
}
storage = session.get(f"{DLM_URL}/storage/query_storage", params=params_loc, headers=bearer, timeout=60)
print(storage.json())
# initialise this storage (if it doesn’t already exist)
params_loc= {
  "storage_name": "MyDisk",
  "location_id": location_id,
  "storage_type": "disk",
  "storage_interface": "posix",
  "storage_capacity": 100000000,
}
storage = session.post(f"{DLM_URL}/storage/init_storage", params=params_loc, headers=bearer, timeout=60)
print(storage.json())
# get the storage_id
storage_id = storage.json()[0]["storage_id"]

# check if a storage config for this storage is already known to DLM
config = session.get(f"{DLM_URL}/storage/get_storage_config", params={"storage_id": storage_id}, headers=bearer, timeout=60)
print(config.json())
# supply an rclone config for this storage (if it doesn’t already exist)
params_config = {
  "config": {
    "name": "MyDisk",
    "type":"local",
    "parameters":{},
  }
}
config = session.post(f"{DLM_URL}/storage/create_storage_config", params=params_config, headers=bearer, timeout=60)
print(config.json())

# register a data item
params_item = {
  "item_name": "/my/ingest/item",
  "uri": "",
  "storage_name": "MyDisk",
  "storage_id": "f3532560-2338-48a7-bba3-f389ad4a3285",
  # "metadata": None,
  # "item_format": None,
  # "eb_id": None,
}
response = session.post(f"{DLM_URL}/ingest/register_data_item", params=params_item, headers=bearer, timeout=60)
print(response.json())

# trigger a migration from storage to storage
params = {
  "item_name": "/my/ingest/item",
  "destination_id": destination_id,
  "path": ""
}
response = session.post(f"{DLM_URL}/migration/copy_data_item", params=params, headers=bearer, timeout=60)
print(response.json())

# list items and their locations
params = {
  "item_name": "/my/ingest/item",
}
response = session.get(f"{DLM_URL}/request/query_data_item", params=params, headers=bearer, timeout=60)
print(response.json())

```

## ska-dlm python methods

Similar to the example above, the source code below is a typical example using python methods.

```python
from ska_dlm import dlm_storage, dlm_ingest

location_name="ThisLocationName"
location_type="ThisLocationType"

# check if the location 'ThisLocationName' is already known to DLM
dlm_storage.query_location(location_name=location_name)
# initialise the location (if it doesn't already exist)
location_id = dlm_storage.init_location(location_name, location_type)

# check if the storage 'MyDisk' is already known to DLM
dlm_storage.query_storage(storage_name="MyDisk")
# initialise the storage (if it doesn't already exist)
storage_id = dlm_storage.init_storage(
   storage_name="MyDisk",
   location_id=location_id,
   storage_type="disk",
   storage_interface="posix",
   storage_capacity=100000000,
)

# supply an rclone config for this storage (if it doesn't already exist)
config = {"name":"MyDisk","type":"local", "parameters":{}}
config_id = dlm_storage.create_storage_config(storage_id=storage_id, config=config)

# register a data item
uid = dlm_ingest.register_data_item(
    "/my/ingest/item", "", "MyDisk", metadata={"execution_block": "eb-m001-20191031-12345"}
)
```

## ska-dlm CLI interface

Lastly, the source code below is a typical example using CLI commands.

```bash
# check if the location MyHost already exists
ska-dlm storage query-location --location-name MyHost
# initialise location (if it doesn't already exist)
ska-dlm storage init-location MyHost server

# check if the storage MyDisk already exists
ska-dlm storage query-storage --storage-name MyDisk
# initialise storage (if it doesn't already exist)
ska-dlm storage init-storage MyDisk disk posix --location-name MyHost

# check if a storage config for MyDisk is already known to DLM
ska-dlm storage get-storage-config --storage-name MyDisk
# create a storage config for MyDisk (if it doesn't already exist)
ska-dlm storage create-storage-config '{"name": "MyDisk","type":"local","parameters":{}}' --storage-id '<the storage id received above>'

# check for existing data items called test_item_name
ska-dlm request query-data-item --item-name test_item_name
# register data item
ska-dlm ingest register-data-item test_item_name --storage-name MyDisk --metadata='{"execution_block":"eb-m001-20191031-12345"}'

# if you can't find the command you need, follow the help prompts
ska-dlm --help
```


## Step 7: Access via Data Product Dashboard

At time of writing, here are the known medium-term deployments of the DLM system:

| Location                         | Data Lifecycle Management URL           | Data Product Dashboard URL                                                  |
| -------------------------------- | --------------------------------------- | --------------------------------------------------------------------------- |
| DP Integration (yanda namespace) | https://sdhp.stfc.skao.int/dp-yanda/dlm | https://sdhp.stfc.skao.int/integration-ska-dataproduct-dashboard/dashboard/ |
