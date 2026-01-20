# Version History

## Development

### Changed

* Changed rclone mount path to /dlm

### Fixed

* Verify that the user has CREATE permission in the DB before attempting to create a schema
* Fixed the error 'bearer_token' referenced before assignment
* Correctly handle the state of a data item after a failed or successful transfer
* Ensure DLM schema is created and search_path is set before running SQL scripts

### Added

* Add ability to add storage endpoint configuration to storage manager on startup
* Add ability to distribute rclone public key via REST endpoint get_ssh_public_key()

## 1.2.0

### Removed

* Remove ALTER TABLE ownership statements.
* Remove hardcoded `public` schema references in SQL scripts

### Changed

* Changed data_item.metadata column type from json to jsonb.

### Added

* Created common_types.py file for centralised type management.
* List of location facilities, as a lookup table
* ENUM definitions for location_type, location_country, config_type, storage_type, storage_interface, phase_type, item_state, checksum_method and mime_type.
* Set up the Helm chart infrastructure to support database patch releases via versioned SQL files.
* Added a patch SQL script for v1.1.2

## 1.1.3

* Add optional `root_path` to rclone config and rc commands

## 1.1.2

### Deprecated

* Deprecates 1.1.1 which had a CI failure (digicert) during OCI image build.

## 1.1.1

### Changed

* Fixed the RCLONE url line in k8s configmap.

## 1.1.0

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
