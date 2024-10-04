# ska-data-lifecycle

## Introduction

The SKA data lifecycle management system (DLM) is designed to manage all intermediate and final data products of the SKA. Data products in the context of the DLM can be any digital asset from any subsystem, which needs to be persisted for a certain amount of time and made resilient against loss to a certain degree. The system will enable the implementation of the FAIR principles for SKA data products. Findability is supported by high and low level search interfaces, Accessibility by providing access to the products through standard methods, Interoperability by ensuring that the product descriptions are adhering to IVOA or other applicable standards and Reusability by maintaining the product quality, storage infrastructure and access over the whole lifetime of the products.

The DLM is designed as a service oriented system sitting on-top of a database. The external interfaces and APIs are based on the REST paradigm. The deployed system will need to be highly available and dependable, since the whole observatory and all its internal and external users will eventually depend on the DLM functioning properly. The number and frequency of transactions as well as the total data volume managed by the DLM will be very significant and thus the system will need to consider scalability as one of the main drivers for the implementation.

The current design consists of five services and this repository is organised accordingly:

- Database management service (DLMdb)
- Ingest management service (DLMingest)
- Request management service (DLMrequest)
- Storage management service (DLMstorage)
- Migration management service (DLMmigration)

## Installation
The repository contains helm charts to install the services, including the DB. However, the DLM in operations is supposed to run continuously and use SKAO-wide services like a HA DB service as well as the authentication system.

## Testing

### Test against Docker Compose

#### Run tests locally

Python testing is available on the local machine using poetry virtual environments. First install and enter a poetry shell:

```bash
poetry install
poetry shell
```

Subsequent testing can be performed using the command:

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

The test platform makes REST requests to DLM services and are proxied through the `dlm_gateway`.

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

DLM also provides a helm chart tested weekly that can also be tested locally using Minikube. The following commands only need to be executed once to prepare a test environment.

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
2. Contact the gateway to exchange the API token for a session cookie
3. Determine the location of the files you wish to add
4. Register that location with the DLM system. Note the location must be accessible (via rclone) from the DLM
5. Ingest the files into DLM one-by-one
6. Access/query the items via the ska-dataproduct-dashboard

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

Interaction with the DLM is also possible via the REST API. The source code below is a typical example.

```python
# this URL is for DLM deployment in the Yanda namespace on the DP integration cluster
# other known locations are shown below
DLM_URL = "https://sdhp.stfc.skao.int/dp-yanda/dlm"

# exchange the token for a session cookie
from requests import Session
session = Session()
bearer = {"Authorization": f"Bearer {your token}"}
response = session.post(f"{DLM_URL}/start_session", headers=bearer, timeout=60)
response.raise_for_status()

# create a name for this storage location
location_name="ThisLocationName"

# check if this storage location is already known to DLM
#location = dlm_storage.query_location(location_name=location_name)
params = {"location_name": location_name}
location = session.get(f"{DLM_URL}/storage/query_location", params=params, timeout=60)
print(location.json())

# otherwise, register this location:
#location = dlm_storage.init_location(location_name, "SKAO Data Centre")
params = {
  "location_name": location_name,
  "location_facility": "SKAO Data Centre",
}

location = session.post(f"{DLM_URL}/storage/init_location", params=params, timeout=60)
print(location.json())

# get the location id
location_id = location.json()[0]["location_id"]

# initialise a storage, if it doesn’t already exist:
#uuid = dlm_storage.init_storage(
#    storage_name="MyDisk",
#    location_id=location_id,
#    storage_type="disk",
#    storage_interface="posix",
#    storage_capacity=100000000,
#)
params = {
  storage_name: "MyDisk",
  location_id: location_id,
  storage_type: "disk",
  storage_interface: "posix",
  storage_capacity: 100000000,
}
storage = session.post(f"{DLM_URL}/storage/init_storage", params=params, timeout=60)
print(storage.json())

# supply a rclone config for this storage, if it doesn’t already exist
#config = '{"name":"MyDisk","type":"local", "parameters":{}}'
#config_id = dlm_storage.create_storage_config(uuid, config=config)
params = {
  config: {
    "name": "MyDisk",
    "type":"local",
    "parameters":{},
  }
}
config = session.post(f"{DLM_URL}/storage/create_storage_config", params=params, timeout=60)
print(config.json())


# then begin adding data items
#uid = dlm_ingest.register_data_item(
#    "/my/ingest/item",
#    path,
#    "MyDisk",
#    metadata=None
#)
params = {
  item_name: "/my/ingest/item",
  uri: "/some/path/to/the/file",
  storage_name: "MyDisk",
  storage_id: "",
  metadata: None,
  item_format: None,
  eb_id: None,
}
response = session.post(f"{DLM_URL}/ingest/register_data_item", params=params, timeout=60)
print(response.json())

```


## Known DLM deployments

At time of writing, here are the known medium-term deployments of the DLM system:

| Location                         | Data Lifecycle Management URL           | Data Product Dashboard URL                                                  |
| -------------------------------- | --------------------------------------- | --------------------------------------------------------------------------- |
| DP Integration (yanda namespace) | https://sdhp.stfc.skao.int/dp-yanda/dlm | https://sdhp.stfc.skao.int/integration-ska-dataproduct-dashboard/dashboard/ |
