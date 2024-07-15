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
docker-compose -f tests/testrunner.docker-compose.yaml build

# Run the test runner
docker-compose --file tests/testrunner.docker-compose.yaml run dlm_testrunner

# Or run tests locally
pytest --env local

# Teardown any remaining services
docker-compose --file tests/testrunner.docker-compose.yaml down
```

#### Authentication

By default the test platform uses OAuth authentication.

To turn it off set:
- In `services.docker-compose.yaml`, section `dlm_gateway`, set `AUTH: "0"`.
- Run tests: `pytest --env local --auth 0`


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
