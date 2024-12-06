# ska-data-lifecycle

## Introduction

The SKA data lifecycle management system (DLM) is designed to manage all intermediate and final data products of the SKA. Data products in the context of the DLM can be any digital asset from any subsystem, which needs to be persisted for a certain amount of time and made resilient against loss to a certain degree. The system will enable the implementation of the FAIR principles for SKA data products. Findability is supported by high and low level search interfaces, Accessibility by providing access to the products through standard methods, Interoperability by ensuring that the product descriptions are adhering to IVOA or other applicable standards and Reusability by maintaining the product quality, storage infrastructure and access over the whole lifetime of the products.

The DLM is designed as a service oriented system sitting on-top of a database. The external interfaces and APIs are based on the REST paradigm. The deployed system will need to be highly available and dependable, since the whole observatory and all its internal and external users will eventually depend on the DLM functioning properly. The number and frequency of transactions as well as the total data volume managed by the DLM will be very significant and thus the system will need to consider scalability as one of the main drivers for the implementation.

The current design consists of five modules/services and this repository is organised accordingly:

- Database management service (DLMdb)
- Ingest management service (DLMingest)
- Request management service (DLMrequest)
- Storage management service (DLMstorage)
- Migration management service (DLMmigration)

In addition we have implemented an AAA API gateway to enable testing of the authentication and authorization functionality of the SKA-DLM. This is run locally against a Keycloak authentication layer, which is started inside a docker container. In production the gateway and the Keycloak container will be replaced by a SKA wide AAA gateway running against the SKA Entra authentication layer.

## Installation
The repository contains helm charts to install the services, including the DB. However, in operations the DLM is supposed to run continuously and use SKAO-wide services like a HA DB service as well as the authentication system. Thus this is not really practical for any evaluation or even DLM internal testing.

## SKA-DLM evaluation environment

If you want to start all the services locally for evaluation purposes you can use the command:

```bash
docker compose --file tests/dlm.docker-compose.yaml up
```
That also enables all the REST interfaces and they can be explored on their individual ports by opening browser pages:

- http://localhost:8000/docs for the AAA API gateway
- http://localhost:8001/docs for the Ingest Manager REST API
- http://localhost:8002/docs for the Request Manager REST API
- http://localhost:8003/docs for the Storage Manager service REST API
- http://localhost:8004/docs for the Migration Manager REST API

 To stop that environment again use the command:

 ```bash
 docker compose --file tests/dlm.docker-compose.yaml down
 ```

## Testing
In order to support mutiple test environments, the DLM can be build and deployed in a variety of ways, depending on the use case and scenario.

### Test against Docker Compose
For code developers all tests can be executed without having to rely on the complexity of the Kubernetes environment.

#### Run full test suite locally

Python testing is available on the local machine using poetry virtual environments. First clone the repo:

```bash
git clone --recurse-submodules https://gitlab.com/ska-telescope/ska-data-lifecycle.git
```

Then install the package and enter a poetry shell:

```bash
cd ska-data-lifecycle
poetry install
poetry shell
```

Subsequently, the tests can be executed using the command:

```bash
make python-test
```

#### Run tests using a Docker Testrunner

A test runner Dockerfile is provided to support local development with packages that may be difficult to install. The following command will run the same python tests inside docker containers:
```sh
make docker-test
```

#### Manual

Alternatively, the following relevant docker compose commands can be mixed and matched to achieve the same result as the above make targets:


```sh
# Rebuild any changed Dockerfile dependencies
docker compose -f tests/testrunner.docker-compose.yaml build

# Run the test runner
docker compose --file tests/testrunner.docker-compose.yaml run dlm_testrunner

# Or run tests locally
pytest --env local

# Teardown any remaining services
docker compose --file tests/testrunner.docker-compose.yaml down
```

#### FastAPI and Authentication

The REST requests issued through the test environment to DLM services are proxied through the `dlm_gateway`.

The `dlm_gateway` checks the destination, unpacks the token and checks the permissions based on the user profile.

If the user has the correct permission then the REST call will be proxied to the correct DLM service. If unauthorised a HTTP 401 or 403 error will be returned.

To run manually:

```sh
# Rebuild any changed Dockerfile dependencies
docker compose -f tests/services.docker-compose.yaml build

# Run services
docker compose -f tests/services.docker-compose.yaml up

# Or run tests locally
pytest --env local --auth 1

```

To turn off authentication:
* In `services.docker-compose.yaml`, section `dlm_gateway`, set `AUTH: "0"`.
* Run tests: `pytest --env local --auth 0`


### Test against Helm Chart

DLM also provides a helm chart tested weekly through the SKA gitlab test runners that can also be executed locally using Minikube. The following commands only need to be executed once to prepare a test environment.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
minikube start --disk-size 64g --cpus=6 --memory=16384
minikube addons enable ingress

ifeq ($(shell uname -m), arm64)
  # Use tunnel on M-Series MacOS
  minikube tunnel
endif
```

Tests can then be run using the command:

```sh
make k8s-test
```

For more information see [helm chart README.md](./charts/ska-dlm/README.md)


## Example Usage

Typical usage of the DLM:

1. Obtain an API token, authorizing use of the DLM by a specific user
2. Determine the location of the files you wish to add
3. Register that location with the DLM system. Note the location must be accessible (via rclone) from the DLM
4. Ingest the files into DLM one-by-one
5. Instruct DLM to migrate the newly ingested item to a secondary storage
6. Query the location of all copies of the item
7. Access the items via the ska-dataproduct-dashboard

### Step 1: Obtain an API token

To obtain an API token:

* Open an browser and go to the `/token_by_auth_flow` endpoint on the DLM server URL. For example: https://sdhp.stfc.skao.int/dp-yanda/dlm/token_by_auth_flow.
* Login with your SKAO credentials
* If successful, a token will be returned. Copy the token.

### Steps 2-6: Data Lifecycle Management

Once a token is ready, interactions with DLM can be done in two ways:

1. ska-dlm-client - a standalone DLM client that can be configured to automatically ingest data items
2. ska-dlm REST API - a (more) manual way to configure storage locations and ingest data items

### ska-dlm-client

The ska-dlm-client is the recommended way of using the DLM. Once configured, the ska-dlm-client will trigger on creation of a new file, or on reception of a kafka message, automatically ingesting the specified item into the DLM.

For more complete information, refer to the ska-dlm-client [repository](https://gitlab.com/ska-telescope/ska-dlm-client/) and [readthedocs](https://ska-telescope-ska-dlm-client.readthedocs.io/en/latest/).

### ska-dlm REST API

Interaction with the DLM is also possible via the REST API. The source code below is a typical example. The comments preceding each REST call are the python method alternatives.

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

# check if this location is already known to DLM
#location = dlm_storage.query_location(location_name=location_name)
params = {"location_name": location_name}
session = Session()
location = session.get(f"{DLM_URL}/storage/query_location", params=params, headers=bearer, timeout=60)
print(location.json())

# otherwise, register this location:
#location = dlm_storage.init_location(location_name, location_type)
params = {
  "location_name": location_name,
  "location_type": location_type,
}

location = session.post(f"{DLM_URL}/storage/init_location", params=params, headers=bearer, timeout=60)
print(location.json())

# get the location id
location_id = location.json()[0]["location_id"]

# check if this storage is already known to DLM
params = {"storage_name": CONFIG.storage.name}
storage = session.get(f"{CONFIG.dlm.storage_url}/storage/query_storage", params=params, timeout=60)
print(storage.json())

# initialise a storage, if it doesn’t already exist:
#uuid = dlm_storage.init_storage(
#    storage_name="MyDisk",
#    location_id=location_id,
#    storage_type="disk",
#    storage_interface="posix",
#    storage_capacity=100000000,
#)
params = {
  "storage_name": "MyDisk",
  "location_id": location_id,
  "storage_type": "disk",
  "storage_interface": "posix",
  "storage_capacity": 100000000,
}
storage = session.post(f"{DLM_URL}/storage/init_storage", params=params, headers=bearer, timeout=60)
print(storage.json())

# get the storage_id
storage_id = storage.json()[0]["storage_id"]

# check if a storage config is already known to DLM
params = {"storage_id": storage_id}
config = session.get(f"{CONFIG.dlm.storage_url}/storage/get_storage_config", params=params, timeout=60)
print(config.json())

# supply a rclone config for this storage, if it doesn’t already exist
#config = '{"name":"MyDisk","type":"local", "parameters":{}}'
#config_id = dlm_storage.create_storage_config(uuid, config=config)
params = {
  "config": {
    "name": "MyDisk",
    "type":"local",
    "parameters":{},
  }
}
config = session.post(f"{DLM_URL}/storage/create_storage_config", params=params, headers=bearer, timeout=60)
print(config.json())

# then begin adding data items
#uid = dlm_ingest.register_data_item(
#    "/my/ingest/item",
#    path,
#    "MyDisk",
#    metadata=None
#)
params = {
  "item_name": "/my/ingest/item",
  "uri": "/some/path/to/the/file",
  "storage_name": "MyDisk",
  "storage_id": "",
  "metadata": None,
  "item_format": None,
  "eb_id": None,
}
response = session.post(f"{DLM_URL}/ingest/register_data_item", params=params, headers=bearer, timeout=60)
print(response.json())

# trigger a migration from storage to storage
params = {
  "item_name": "/my/ingest/item",
  "destination_id": destination_id,
  "path": ""
}
response = session.post(f"{DLM_URL}/migration/copy_data_item", params=params, timeout=60)
print(response.json())

# list items and their locations
params = {
  "item_name": "/my/ingest/item",
}
response = session.get(f"{DLM_URL}/request/query_data_item", params=params, timeout=60)
print(response.json())

```


### Step 8: Access via Data Product Dashboard

At time of writing, here are the known medium-term deployments of the DLM system:

| Location                         | Data Lifecycle Management URL           | Data Product Dashboard URL                                                  |
| -------------------------------- | --------------------------------------- | --------------------------------------------------------------------------- |
| DP Integration (yanda namespace) | https://sdhp.stfc.skao.int/dp-yanda/dlm | https://sdhp.stfc.skao.int/integration-ska-dataproduct-dashboard/dashboard/ |
