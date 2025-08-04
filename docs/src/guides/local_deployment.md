# Local Development

Interact with DLM by the way of local Docker deployment, using python methods or the CLI interface.
From within your DLM directory, start the DLM services first, e.g., by running:
```
docker compose -f tests/services.docker-compose.yaml -p dlm-test-services build
docker compose -f tests/services.docker-compose.yaml -p dlm-test-services up -d
```

## Register and Migrate Example Data Item

The following sections describe how to perform a data item registration and migration example from within a DLM server without the RESTful interface. This can be performed either on a developer machine after installing the `ska-data-lifecycle` package, or via a remote session to a DLM server instance.

(local-development-cli)=
### Command Line Interface

```bash
# check if the location MyLocation already exists
ska-dlm storage query-location --location-name MyLocation
# initialise location (if it doesn't already exist)
ska-dlm storage init-location MyLocation external

# check if the storage MyDisk already exists
ska-dlm storage query-storage --storage-name MyDisk
# initialise storage with root directory "/" (if it doesn't already exist)
ska-dlm storage init-storage MyDisk filesystem posix / --location-name MyLocation

# check if a storage config for MyDisk is already known to DLM
ska-dlm storage get-storage-config --storage-name MyDisk
# create a storage config for MyDisk (if one doesn't already exist). The default `config_type` is rclone.
ska-dlm storage create-storage-config '{"name":"MyDisk", "type":"alias", "parameters":{"remote": "/"}}' \
--storage-id '<the storage id received above>'

# register an existing data item inside the Docker container (e.g., /etc/os-release)
ska-dlm ingest register-data-item test_item_name etc/os-release --storage-name MyDisk \
--metadata='{"execution_block":"eb-m001-20191031-12345"}'

# query for data items called "test_item_name"
ska-dlm data-item query-data-item --item-name test_item_name

# migrate an item from one storage to another
# register a second storage
ska-dlm storage init-storage MyDisk2 filesystem posix / --location-name MyLocation

# supply a storage configuration
ska-dlm storage create-storage-config '{"name":"MyDisk2", "type":"alias", "parameters":{"remote": "/"}}' \
--storage-id '<the storage id received above>'

# copy your data item from MyDisk to MyDisk2
ska-dlm migration copy-data-item --item-name "test_item_name" --destination-name "MyDisk2" \
--path "/data/test_item"

# query for all instances of "test_item_name"
ska-dlm data-item query-data-item --item-name "test_item_name"

# if you can't find the command you need, follow the help prompts
ska-dlm --help
```

(local-development-python-script)=
### Python module interface

```python
from ska_dlm import dlm_storage, dlm_ingest, dlm_migration, dlm_request

location_name = "MyLocation"
location_type = "external"

# check if the location 'MyLocation' is already known to DLM
dlm_storage.query_location(location_name=location_name)
# initialise the location (if it doesn't already exist)
location_id = dlm_storage.init_location(location_name, location_type)

# check if the storage 'MyDisk' is already known to DLM
dlm_storage.query_storage(storage_name="MyDisk")
# initialise the storage (if it doesn't already exist)
storage_id = dlm_storage.init_storage(
    storage_name="MyDisk",
    root_directory="/",
    location_id=location_id,
    storage_type="filesystem",
    storage_interface="posix",
    storage_capacity=100000000,
)

# check if a storage configuration for 'MyDisk' already exists
dlm_storage.get_storage_config(storage_name="MyDisk")
# supply a storage_config, if one doesn't already exist (default `config_type` is rclone)
config = {"name": "MyDisk", "type": "alias", "parameters": {"remote": "/"}}
config_id = dlm_storage.create_storage_config(storage_id=storage_id, config=config)

# register a data item
uid = dlm_ingest.register_data_item(
    item_name="test_item",
    uri="/etc/os-release",
    storage_name="MyDisk",
    item_type="file",
    metadata={"execution_block": "eb-m001-20191031-12345"},
)

# migrate an item from one storage to another
# register a second storage
storage_id = dlm_storage.init_storage(
    storage_name="MyDisk2",
    root_directory="/",
    location_id=location_id,
    storage_type="filesystem",
    storage_interface="posix",
    storage_capacity=100000000,
)
# supply a storage_config
config = {"name": "MyDisk2", "type": "alias", "parameters": {"remote": "/"}}
config_id = dlm_storage.create_storage_config(storage_id=storage_id, config=config)

# copy "test_item" from MyDisk to MyDisk2
dlm_migration.copy_data_item("test_item", destination_name="MyDisk2", path="/data/test_item")

# query for all instances of "test_item"
dlm_request.query_data_item("test_item")
```

Remember to tear down the services:
```
docker compose -f tests/services.docker-compose.yaml -p dlm-test-services down
```
