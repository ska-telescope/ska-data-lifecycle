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

This repository contains Helm charts for deploying the DLM services, including an optional PostgreSQL database. While the DLM is designed to run in an operational environment using SKAO-managed services (for example, a high-availability database and central authentication), the provided Helm charts support deployment in non-production environments for evaluation and development.

For full instructions on how to deploy the DLM using Helm see [charts/README.md](./charts/ska-dlm/README.md).

## Evaluation environment

If you want to start all the services locally for evaluation purposes you can use the command:

```bash
docker compose --file tests/dlm.docker-compose.yaml up
```

This starts the complete DLM stack and exposes the REST APIs at:

- http://localhost:8000/docs for the AAA API gateway
- http://dlm_ingest.localhost/docs for the Ingest Manager REST API
- http://dlm_request.localhost/docs for the Request Manager REST API
- http://dlm_storage.localhost/docs for the Storage Manager service REST API
- http://dlm_migration.localhost/docs for the Migration Manager REST API

To stop the evaluation environment:

```bash
docker compose --file tests/dlm.docker-compose.yaml down
```

## Development and testing

For local development, the full test suite can be executed using Docker Compose without requiring a Kubernetes environment.

### Local setup

Clone the repository, including its submodules:

```bash
git clone --recurse-submodules https://gitlab.com/ska-telescope/ska-data-lifecycle.git
```

Install the project and its dependencies using Poetry:

```bash
cd ska-data-lifecycle
poetry install
poetry shell
```

### Run unit tests

Run the unit test suite (excluding integration tests):

```bash
make python-test
```

### Run the full test suite

```bash
make docker-test
```

Builds the Docker test environment, runs both the unit and integration tests, and then tears the environment down.

### Run integration tests

```bash
make integration-test
```

Builds the Docker test environment, runs only the integration tests, and then tears the environment down.

### Development mode

The underlying Docker test environment can be started manually without running any tests:

```bash
make all-services-up
```

This starts all services required for the integration test environment, including the test PostgreSQL database, but excluding the `dlm_testrunner` container. During startup, the Storage Manager automatically creates the `SKA-DEV` location endpoint and the `dlm-archive` storage endpoint from the supplied configuration files.

Tests can then be run manually, for example:

```bash
docker compose --file tests/testrunner.docker-compose.yaml -p tests \
  run --rm --no-deps dlm_testrunner
```

When finished, tear the environment down with:

```bash
make all-services-down
```

### FastAPI and Authentication

The REST requests issued through the test environment to DLM services are proxied through the `dlm_gateway`.

The `dlm_gateway` checks the destination, unpacks the token and checks the permissions based on the user profile.

If the user is authorised, the request is proxied to the appropriate DLM service. Unauthorised requests return an HTTP 401 or 403 response.

Authentication is enabled by default in the test environment.


To turn off authentication:
* In `services.docker-compose.yaml`, section `dlm_gateway`, set `AUTH: "0"`.
* Rebuild the services, then run tests, e.g. manually: `pytest --env local --auth 0` (TODO: DMAN-310)


### Test against the Helm chart

DLM also provides a Helm chart that is tested weekly through the SKA GitLab test runners and can also be run locally with Minikube. The following commands only need to be run once to prepare the test environment.

- From the root directory of this repository, install Helm chart dependencies (as defined in `Chart.yaml` / `Chart.lock`):
  ```sh
  make k8s-dep-build
  ```

- Start minikube
```bash
  minikube start --disk-size 64g --cpus=6 --memory=16384
  minikube addons enable ingress
```

- On Apple Silicon Macs, you might also have to start a Minikube tunnel:
```bash
  minikube tunnel
```

- Tests can then be run using the command:
```sh
  make k8s-test
```

For more information see [helm chart README.md](./charts/ska-dlm/README.md)
