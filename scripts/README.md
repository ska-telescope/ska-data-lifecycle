# Benchmark Utilities

## Summary

[Locust](https://docs.locust.io/en/stable/what-is-locust.html) utilities that test the performance of the various DLM subsystems.

* `migration.py`: performs end-to-end data migration tests with performance metrics. 
* `register.py`: performs parallel `register_data_item()` API requests to stress the DLM backend.

## `migration.py` Utility

A configuration file is required for the migration tests.

Within a configuration, a user can:
* Setup multiple storage end points.
* Register multiple data items per storage end point. 
* Perform multiple data item migrations to storage end points.  

### Migration Configuration File

```yaml
- Benchmarks:
    - migration<integer>: can define 1 or many
        - enabled: include migration test (true/false)
        - name: item name
        - uri: relative uri
        - type: file or container
        - source_storage: name of source storage endpoint
        - destination_storage: name of destination storage endpoint

- dlm:
    - url: url of gateway
    - token: access API token
    - migration_polltime: number of seconds delay before checking migration job state

- storage:
    - storage<integer>: can define 1 or many
      - location: name of storage location
      - name: storage name
      - type: type of storage endpoint
      - interface: posix, s3 etc
      - root_directory: root directory of mount point.
      - config: RClone config

```

### Example Configuration

Create a migration configuration file: `migrate.yaml`

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
  migration_polltime: 5

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

### Locust Configuration
Create a locust configuration file: `migrate.conf`

```
host = <url of gateway>
migration_config = <path to the migration config yaml file>
output_file = <output file path of stats>
```

### Usage Steps

1) Create the necessary config files (as above).
2) Ensure that the file or directory, specified by the `benchmarks.migrate<#>.uri` in the migration config file, is already on the source storage endpoint.
3) Manually obtain access token from the DLM auth provider (i.e. https://sdhp.stfc.skao.int/dp-dm/dlm/token_by_auth_flow) and place it in the migration config file under `dlm.token`.
4) Run

```
cd ska-data-lifecycle/
poetry install

cd scripts/benchmark/

locust -f migrate.py --config=migrate.conf
```

5. Then go to the webpage provided on the command line i.e. `http://0.0.0.0:8089` then click START.


### Output

Example of the JSON output.

```json
[
    {
        "migrate1": {
            "migration_id": 89,
            "job_id": 1324,
            "oid": "3396fac2-35f9-441d-9f24-bee47502a3b0",
            "url": "https://dlm_rclone:5572",
            "source_storage_id": "9209d4fe-9794-4257-a5e9-67fdab7dc47c",
            "destination_storage_id": "e482bc74-d822-412d-b994-64bdb741fa26",
            "user": "admin",
            "group": "SKA",
            "job_status": {
                "id": 1324,
                "error": "",
                "group": "job/1324",
                "output": {},
                "endTime": "2025-06-26T05:23:40.402453797Z",
                "success": true,
                "duration": 2.05393371,
                "finished": true,
                "startTime": "2025-06-26T05:23:38.348520046Z"
            },
            "job_stats": {
                "eta": 0,
                "bytes": 1048576000,
                "speed": 512178285.81585526,
                "checks": 0,
                "errors": 0,
                "deletes": 0,
                "renames": 0,
                "transfers": 1,
                "fatalError": false,
                "retryError": false,
                "totalBytes": 1048576000,
                "deletedDirs": 0,
                "elapsedTime": 9.988867754,
                "totalChecks": 0,
                "transferTime": 2.053775584,
                "totalTransfers": 1,
                "serverSideMoves": 0,
                "serverSideCopies": 0,
                "serverSideCopyBytes": 0,
                "serverSideMoveBytes": 0
            },
            "complete": true,
            "date": "2025-06-26T05:23:38.350798",
            "completion_date": null
        }
    },
    {
        "migrate2": {
            "migration_id": 90,
            "job_id": 1326,
            "oid": "7fff8844-2414-44ce-9a02-1dee29f7d316",
            "url": "https://dlm_rclone:5572",
            "source_storage_id": "9209d4fe-9794-4257-a5e9-67fdab7dc47c",
            "destination_storage_id": "08a2dd3b-4c4a-4576-910e-8ac490d425c9",
            "user": "admin",
            "group": "SKA",
            "job_status": {
                "id": 1326,
                "error": "",
                "group": "job/1326",
                "output": {},
                "endTime": "2025-06-26T05:24:27.320082222Z",
                "success": true,
                "duration": 48.865708189,
                "finished": true,
                "startTime": "2025-06-26T05:23:38.454891296Z"
            },
            "job_stats": {
                "eta": 0,
                "bytes": 1048576000,
                "speed": 22204513.526739564,
                "checks": 0,
                "errors": 0,
                "deletes": 0,
                "renames": 0,
                "transfers": 1,
                "fatalError": false,
                "retryError": false,
                "totalBytes": 1048576000,
                "deletedDirs": 0,
                "elapsedTime": 50.016739606,
                "totalChecks": 0,
                "transferTime": 48.643768189,
                "totalTransfers": 1,
                "serverSideMoves": 0,
                "serverSideCopies": 0,
                "serverSideCopyBytes": 0,
                "serverSideMoveBytes": 0
            },
            "complete": true,
            "date": "2025-06-26T05:23:38.457102",
            "completion_date": null
        }
    }
]
```


## `register.py` Utility

### Locust Configuration
Create a locust configuration file: `register.conf`

```
host = <url of gateway>
token = <access API token>
```

### Usage Steps

1) Create the necessary config file(s) (as above).
2) Manually obtain access token from the DLM auth provider (i.e. https://sdhp.stfc.skao.int/dp-dm/dlm/token_by_auth_flow) and place it in the migration config file under `dlm.token`.
3) Run

```
cd ska-data-lifecycle/
poetry install

cd scripts/benchmark/

locust -f register.py --config=register.conf
```

4. Then go to the webpage provided on the command line i.e. `http://0.0.0.0:8089`
5. Can specify the number of parallel users and ramp up time, then click START.