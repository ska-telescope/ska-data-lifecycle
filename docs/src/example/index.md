
# Usage

1. ska-dlm-client — a standalone DLM client that can be configured to automatically ingest data items
2. ska-dlm REST API — a (more) manual way to configure storage locations and ingest data items

## ska-dlm-client

The ska-dlm-client is the recommended way of using the DLM. Once configured, the ska-dlm-client will trigger on creation of a new file, or on reception of a kafka message, automatically ingesting the specified item into the DLM.

For more complete information, refer to the ska-dlm-client [repository](https://gitlab.com/ska-telescope/ska-dlm-client/) and [readthedocs](https://ska-telescope-ska-dlm-client.readthedocs.io/en/latest/).

## Usage on the DP cluster: tutorial

Typical usage of the DLM:

1. Obtain an API token, authorizing use of the DLM by a specific user
2. Determine the location of the files you wish to add
3. Register that location with the DLM system. Note the location must be accessible (via rclone) from the DLM
4. Ingest the files into DLM one-by-one
5. Instruct DLM to migrate the newly ingested item to a secondary storage
6. Query the location of all copies of the item
7. Access the items via the [Data Product Dashboard](https://developer.skao.int/projects/ska-dataproduct-dashboard/en/latest/?badge=latest)

### Step 1: Obtain an API token

To obtain an API token:

* Open a browser and go to the `/token_by_auth_flow` endpoint on the DLM server URL. For example: `https://sdhp.stfc.skao.int/dp-yanda/dlm/token_by_auth_flow`.
* Login with your SKAO credentials
* If successful, a token will be returned. Copy the token.

### Steps 2-6: ska-dlm REST API

The source code below demonstrates how to register a data item on the Acacia storage.

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


# Local development and testing

Interact with the DLM by the way of local Docker deployment, using python methods or the CLI interface.
From within your DLM directory, start the DLM services first, e.g., by running:
`docker compose -f tests/services.docker-compose.yaml -p dlm-test-services build`\
`docker compose -f tests/services.docker-compose.yaml -p dlm-test-services up -d`

## ska-dlm python methods

```python
from ska_dlm import dlm_storage, dlm_ingest, dlm_migration, dlm_request

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
   root_directory="/data/MyDisk",
   location_id=location_id,
   storage_type="disk",
   storage_interface="posix",
   storage_capacity=100000000,
)

# check if an rclone config for 'MyDisk' already exists
dlm_storage.get_storage_config(storage_name="MyDisk")
# supply an rclone config (if it doesn't already exist)
config = {"name":"MyDisk","type":"alias", "parameters":{"remote": "/"}}
config_id = dlm_storage.create_storage_config(storage_id=storage_id, config=config)

# register a data item
uid = dlm_ingest.register_data_item(
    "test_item",
    uri="",
    storage_name="MyDisk",
    item_type="file",
    metadata={"execution_block": "eb-m001-20191031-12345"}
)

# migrate an item from one storage to another
# register a second storage
storage_id = dlm_storage.init_storage(
   storage_name="MyDisk2",
   root_directory="/data/MyDisk2",
   location_id=location_id,
   storage_type="disk",
   storage_interface="posix",
   storage_capacity=100000000,
)
# supply an rclone config
config = {"name":"MyDisk2","type":"alias", "parameters":{"remote": "/"}}
config_id = dlm_storage.create_storage_config(storage_id=storage_id, config=config)

# copy "test_item" from MyDisk to MyDisk2
dlm_migration.copy_data_item("test_item", destination_name="MyDisk2", path="")

# query for all copies of the item
dlm_request.query_data_item("test_item")

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
