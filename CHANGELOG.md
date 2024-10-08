# Version History

## 0.1.0

### Added

* Added FastAPI and Typer paramater documentation
* Added FastAPI and Keycloak OAuth
* Set up k8s tests to run only on CI scheduled builds
* Set up docker-compose as the main test target for gitlab testing
* Add optional pgweb IDE deployment

### Changed

* Decoupled unit testing from Minikube

## 0.0.1

* Bootstrap repo with ska-cookiecutter-pypackage
* Add `ska-dlm` CLI tool with initial set of sub-commands.
* Add base exceptions
* Add DB access utility functions
* Add `ska-dlm` Helm chart
