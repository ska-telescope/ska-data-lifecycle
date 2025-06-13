# Benchmark Utility

## Summary
Utility that allows a user to define multiple migrations between DLM endpoints and dumps the migrationn RClone statistics in JSON format.

## Configuration YAML File
```yaml
- Benchmarks:
    - migration(#): can define 1 or many
        - enabled: include migration test (true/false)
        - name: item name
        - uri: relative uri
        - type: file or container
        - source_storage: name of source storage endpoint
        - destination_storage: name of destination storage endpoint

- dlm:
    - url: url of gateway
    - token: access API token

- storage:
    - storage(#): Can define 1 or many
    - location: name of storage location
    - name: storage name
    - type: type of storage enpoint
    - interface: posix, s3 etc
    - root_directory: root directory of mount point.
    - config: RClone config


### Example
```yaml
benchmarks:

  migrate1:
    enabled: true
    name: test_item
    uri: data/test.bin
    type: file
    source_storage: test_source
    destination_storage: test_destination
    destination_path: data/test_copy.bin

  migrate2:
    enabled: true
    name: test_s3_item
    uri: data/object.bin
    type: file
    source_storage: test_source
    destination_storage: s3_destination
    destination_path: aussrc/object.bin

dlm:
  url: http://localhost:8000/
  token: <token>

storage:
  storage1:
    location: test_location
    name: test_source
    type: disk
    interface: posix
    root_directory: /
    config:
        name: test_source
        type: alias
        parameters: {"remote": "/"}

  storage2:
    location: test_location
    name: test_destination
    type: disk
    interface: posix
    root_directory: /
    config:
        name: test_destination
        type: alias
        parameters: {"remote": "/"}

  storage3:
    location: test_location
    name: s3_destination
    type: disk
    interface: s3
    root_directory: /
    config:
      name: s3
      type: s3
      parameters: {
                  "access_key_id": "<key>",
                  "provider": "Ceph",
                  "secret_access_key": "<secret>",
                  "endpoint": "https://projects.pawsey.org.au"}
```

## Usage

1) Create config file with necessary entries eg. config.yaml
2) Ensure that the file or directory, specified by the migration uri, is already on the source storage endpoint.
3) Manually obtain access token from the DLM auth provider (i.e. https://sdhp.stfc.skao.int/dp-yanda/dlm/token_by_auth_flow) and place it in the config file.
4) Run


```
cd ska-data-lifecycle/

python -m scripts.benchmark --config config.yaml --output bench.json
```
