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
The repository contains helm charts to install the services, including the DB. However, the DLM in operations is supposed to run continuously and use SKAO wide services like a HA DB service as well as the authentication system.

## Testing

### Minikube + Helm One-Time Setup
DLM testing currently depends on the helm chart deployment of services requiring both helm and minikube to be installed on the test runner. The following commands only need to be executed once to prepare a test environment.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
minikube start --disk-size 64g --cpus=6 --memory=16384
minikube addons enable ingress

ifeq ($(shell uname -m), arm64)
  # Use tunnel on M-Series MacOS
  minikube tunnel
endif
```

For more information see [helm chart README.md](./charts/ska-dlm/README.md)


### Run Tests

Python testing is available using poetry virtual environments. First install and enter a poetry shell:

```bash
poetry install
poetry shell
```

Subsequent testing can be performed using only the command:

```bash
make python-test
```


### Docker Setup

There is a Docker version for local development and testing

#### Build the Images

```
docker-compose build
```

#### Run Tests

The following will start all the necessary services and then run the unit tests within its own container

```
docker-compose up
```


#### Development

You can run the services within containers and develop the code in isolation.

```
docker-compose up dlm_db dlm_rclone dlm_postgrest 
```

To run the tests on your own computer ensure --env local is passed to pytest. 

```
pytest --env local tests/integration/test_ska_data_lifecycle.py
```
