# External Storage

(dp-cluster)=
## Ingest and Migrate a Data Item

This section outlines the steps required to ingest and migrate data using the **ska-dlm REST API interface**.

1. Obtain an API token, authorizing use of DLM by a specific user
2. Determine the location of the file(s) you wish to register, and register this location with DLM
3. Register the storage on the DLM system
4. Ensure the storage is accessible (via rclone) from DLM
5. Ingest the files into DLM one-by-one
6. Instruct DLM to migrate the newly ingested item to a secondary storage
7. Query the location of all copies of the item


The source code below demonstrates how to register a data item that resides on external storage (Acacia, located at the Pawsey Centre) while working from the DP platform.


**1. Prepare token to be placed in the header of your REST calls**

* Open a browser and go to the `/token_by_auth_flow` endpoint on the DLM server URL. For example: `https://sdhp.stfc.skao.int/dp-dm/dlm/token_by_auth_flow`.
* Login with your SKAO credentials
* If successful, a token will be returned. Copy the token.

```python
from requests import Session

# this URL is for DLM deployment in the 'dp-dm' namespace on the DP test platform
DLM_URL = "https://sdhp.stfc.skao.int/dp-dm/dlm"
token = <your token>
headers = {"Authorization": f"Bearer {token}"}
session = Session()
```

**2. Check if the desired location (e.g., Pawsey) is already known to DLM**
```python
# create location details
location_name = "Pawsey"
location_type = "low-integration"

location = session.get(
    f"{DLM_URL}/storage/query_location",
    params={"location_name": location_name},
    headers=headers,
    timeout=60,
)
print(location.json())
location_id = location.json()[0]["location_id"]  # if location exists, get the location id
```

*If the desired location doesn't already exist*, initialise it
```python
loc_params = {
    "location_name": location_name,
    "location_type": location_type,
}
location = session.post(
    f"{DLM_URL}/storage/init_location", params=loc_params, headers=headers, timeout=60
)
print(location.json())
location_id = location.json()  # get the location id
```

**3. Check if the desired storage (e.g., Acacia) is already known to DLM**
```python
storage_params = {
    "storage_name": "Acacia",
    "location_id": location_id,
}
storage = session.get(
    f"{DLM_URL}/storage/query_storage", params=storage_params, headers=headers, timeout=60
)
print(storage.json())
storage_id = storage.json()[0]["storage_id"]  # if the storage exists, get the storage id
```

If the desired storage is not listed, register an rclone supported storage endpoint where `storage_interface` is the rclone config type. For more information, refer to the [rclone configuration docs](https://rclone.org/docs/#configure).
```python
storage_params = {
    "storage_name": "Acacia",
    "root_directory": "rascil", # example of an existing directory
    "location_id": location_id,
    "storage_type": "objectstore",
    "storage_interface": "s3",  # rclone config type
    "storage_capacity": 100000000,
}
storage = session.post(
    f"{DLM_URL}/storage/init_storage",
    params=storage_params,
    headers=headers,
    timeout=60,
)
print(storage.json())
storage_id = storage.json()  # get the storage_id
```
**4. Check what rclone configs for the desired storage are already known to DLM**

```python
config = session.get(
    f"{DLM_URL}/storage/get_storage_config",
    params={"storage_id": storage_id},
    headers=headers,
    timeout=60,
)
print(config.json())
```
If you need to, supply an rclone config for the desired storage. For further details, refer to the [rclone configuration docs](https://rclone.org/docs/#configure).
```python
acacia_config = {
    "name": "myacacia",
    "type": "s3",
    "parameters": {
        "access_key_id": "<your-access-key-id>",
        "endpoint": "https://projects.pawsey.org.au",
        "provider": "Ceph",
        "secret_access_key": "<your-secret-access-key>",
    },
}
config = session.post(
    f"{DLM_URL}/storage/create_storage_config",
    params={"storage_id": storage_id},
    json=acacia_config,
    headers=headers,
    timeout=60,
)
print(config.json())
```
**5. Register a data item that exists on the desired storage**
```python
item_params = {
    "item_name": "test_item",
    "uri": "1197634128-cal_avg32.ms.tar.xj", # randomly chosen example file
    "storage_name": "Acacia",
    "storage_id": storage_id,
}
json_body = {"execution_block": "eb-m001-20191031-12345"}  # metadata example
acacia_response = session.post(
    f"{DLM_URL}/ingest/register_data_item",
    params=item_params,
    json=json_body,
    headers=headers,
    timeout=60,
)
print(acacia_response.json())
```
**6. Trigger a migration to a second storage.**
_If your destination storage isn't known to DLM, first initialise it (using the method above)_.
```python
migration_params = {
    "item_name": "test_item",
    "destination_name": <dest_storage>,
    "path": <dest_path>,
}
migration_response = session.post(
    f"{DLM_URL}/migration/copy_data_item",
    params=migration_params,
    headers=headers,
    timeout=60,
)
print(migration_response.json())
```
**7. Query for all copies of the data item**
```python
response = session.get(
    f"{DLM_URL}/request/query_data_item",
    params={"item_name": "test_item"},
    headers=headers,
    timeout=60,
)
print(response.json())
```
