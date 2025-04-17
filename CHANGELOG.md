# Version History

## Development

### Added

* Support for Vault Secret Operator
* Optional date and storage_id filters for migration query

### Removed

* Support for Vault Agent Injector

### Changed

* Removed use of .svc.cluster.local from service names for compatability with LOW cluster.

## 1.0.0

### Added

* Added request service `PATCH` endpoints for modifying data items.
* Added benchmark utility for DLM migration.
* PostgREST connection details can be now obtained from Vault.

### Removed

* Removed dependency on `casacore` and `ska-sdp-metadata-generator` module.
* Removed HTTP POST call to the Data Product Dashboard.

### Changed

* Updated the `requests.post` call in the client `register_data_item` function to send metadata as JSON in the request body.
* Updated `register_data_item` with option `do_storage_access_check` to provide the client the ability to tell DLM server to not do `rclone_access` check.

## 0.2.0

### Added

* Added CICD deployment jobs for 3 targets: `ci-dev`, `integration` and `staging`
* Added configurable shared PVC options for Helm chart services
* Added data product api connection strings to Helm chart

### Changed

* Changed helm chart pod names to contain instance name
* Changed `migration/copy_data_item` endpoint from `GET` to `POST`
* Changed `storage/init_storage` options from `json_data` params to request body.
* Changed from gateway session authentication to bearer tokens

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
