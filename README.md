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

For more detailed information, see [ReadTheDocs](https://developer.skao.int/projects/ska-data-lifecycle/en/latest/?badge=latest)

## Installation
This repository contains Helm charts for deploying the DLM services, including an optional PostgreSQL database. While the DLM is designed to run in an operational environment using SKAO-managed services (e.g., a high-availability database and central authentication), the included charts provide a working configuration suitable for local development, internal testing, and evaluation.
For full instructions on how to deploy the DLM using Helm see [charts/README.md](./charts/ska-dlm/README.md).

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
docker compose -f tests/testrunner.docker-compose.yaml -p dlm-test-services build

# Run the test runner
docker compose -f tests/testrunner.docker-compose.yaml -p dlm-test-services run dlm_testrunner

# Or run tests locally
pytest --env local

# Teardown any remaining services
docker compose -f tests/testrunner.docker-compose.yaml -p dlm-test-services down
```

#### FastAPI and Authentication

The REST requests issued through the test environment to DLM services are proxied through the `dlm_gateway`.

The `dlm_gateway` checks the destination, unpacks the token and checks the permissions based on the user profile.

If the user has the correct permission then the REST call will be proxied to the correct DLM service. If unauthorised a HTTP 401 or 403 error will be returned.

To run manually:

```sh
# Rebuild any changed Dockerfile dependencies
docker compose -f tests/services.docker-compose.yaml -p dlm-test-services build

# Run services
docker compose -f tests/services.docker-compose.yaml -p dlm-test-services up

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
