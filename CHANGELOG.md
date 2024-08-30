# Version History

## 0.0.1

* Added Keycloak OAuth2 authentication to dev deployments
* Addeed FastAPI services for requests, ingest, storage, and migration
* Set up k8s tests to run only on CI scheduled builds
* Set up docker-compose as the main test target for gitlab testing
* Decouple DLM unit testing from Minikube
* Added database pgweb IDE to dev deployments

## Unreleased

* Bootstrap repo with ska-cookiecutter-pypackage
* Add `ska-dlm` CLI tool with initial set of sub-commands.
* Add base exceptions
* Add DB access utility functions
* Add `ska-dlm` Helm chart
