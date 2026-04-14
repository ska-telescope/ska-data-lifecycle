# SKA Data Lifecycle Management Chart

This chart installs the DLM services, including PostgREST and, optionally, a PostgreSQL instance via the Bitnami chart.

The main configuration options are:

 * `global.ingress.enabled`: If set to false, no Ingress resources will be created, meaning external access to services like pgweb and PostgREST will be unavailable. Set to true to expose these services outside the cluster.
 * `postgresql.enabled`: If true, a PostgreSQL instance will be deployed via the Bitnami chart. Otherwise, an external PostgreSQL service is assumed.
 * `postgresql.primary.persistence.enabled`: If enabled, PostgreSQL will persist data between executions, otherwise it will start from scratch each time.
 * `database.migration.enabled`: If true, the DLM tables will be created automatically in the database. Must be true for any base or patch migration to run. See [Database Migrations](#database-migrations) for more information.
 * `database.migration.image`: The Docker image used for executing SQL migration jobs (default: `postgres`)
 * `database.migration.version`: Version tag of the migration image (default: 17.4).

## Authentication

DB authentication details for PostgREST are stored in a Kubernetes `Secret`.
The `Secret` is **always** automatically created to point to the internal PostgreSQL server, if that is enabled.
Otherwise, the following Helm values under `postgrest.db_auth_secret` take effect:

 * `create`: Whether to create a `Secret` or not.
   * If unset, an existing one has to be provided via `name`.
   * If set, the `Secret` is created from the Vault contents at `vault.{mount,path,type}`.
 * In both cases, the `Secret` should provide the following keys: `PGHOST`, `PGUSER`, `PGPASSWORD` and `PGDATABASE`.

## Shared volume

In order for data to be shared between pods, it's important to ensure that the PVC `global.sharedpvc` is instantiated.

RClone generates an SSH key pair which it shares with the Storage Manager via `global.sharedpvc` so it can be distributed to storage end points via the REST endpoint `get_ssh_public_key`.

## Rclone Helm Chart `secret` values

 * `secret`:
    * `enabled`: if `true`, then enable rclone secrets.
    * `name`: name of an existing secret created by an external mechanism. This will only be used if `secret.vault.enabled` is `false` and it's not empty.
    * `mountPoint`: secrets mount point in rclone pod.
    * `ssl_cert_name`: name of the SSL cert secret that exists in the directory `mountPoint`. If empty then SSL will be disabled.
    * `ssl_key_name`: name of the SSL key secret that exists in the directory `mountPoint`. If empty then SSL will be disabled.
    * `vault`:
        * `enabled`: if `true`, then use the vault to populate the secret. `secret.enabled` must also `true`.
        * `mount`: vault root.
        * `type`: vault engine type, defaults to `kv-v2`
        * `path`: vault path.

## Database Migrations

Database migrations are managed by the `ska-db-migrations` subchart using Liquibase. Migrations are automatically executed by a Kubernetes Job as part of the Helm deployment process.

To configure migrations:

* `ska-db-migrations.runMigrations`: Set to `true` (default) to run migrations on deploy.
* `ska-db-migrations.liquibase.contextFilter`:
    * Set to `""` (empty, default) to run all changesets, including schema creation if the role has permission.
    * Set to `"unprivileged"` to run only standard application schema changes, skipping steps that require database-level privileges (like creating the schema itself). This is intended for use with sandboxed roles.

SQL migration scripts are located in `initdb-scripts/` (base schema) and `patches/` (updates). These are organized by the master `changelog.yaml` file.


## Storage Manager

There is an option to create multiple locations when the storage manager starts by adding the following list of named values:
```
locations:
    - name: name of the location (free text – no enum or lookup constraints)
      type: type of storage ("local-dev", "low-integration", "mid-integration", "low-operations", "mid-operations")
      country: country where storage is located ("AU", "AZ", "UK")
      city: city where the storage is located
      facility: specific location ("SRC", "STFC", "AWS", "Google", "Pawsey Centre", "external", "local")

    - name: ...
      type: ...
```

There is an option to create multiple storage endpoints when the storage manager starts by adding the following list of named values:

```
endpoints:
  - name: storage name (free text – no enum or lookup constraints)
  - location: name of existing location endpoint
  - storage_type: type of storage endpoint ("filesystem", "objectstore", "tape")
  - interface: storage interface ("posix", "s3", "sftp", "https")
  - root_directory: root directory of mount point.
  - config:
      - name: rclone storage name
      - type: rclone storage type i.e. ("s3", "alias", ...)
      - parameters: rclone parameters as a json dictionary

  - name: ...
  - location: ...
```

* Set `storage.endpointSecretName` to the name of predefined k8 secret. The secret can contain the key value pairs of rclone secrets for a named storage endpoint. The `config.parameters` value for an endpoint will be replaced by the secret value if the secret key matches the name of the storage endpoint.
For example, if the `config.name` is `test` then the it will look for the key value pair with the name `test` and then replace `config.paramaters` with the keys value.
If `storage.endpointSecretName` is empty, then the `config.parameters` will remained unchanged.

### Storage Endpoint Examples

#### SFTP Endpoint
```
  endpoints:
    - name: SFTEndpoint
      location: DP
      storage_type: filesystem
      interface: posix
      storage_phase: GAS
      root_directory: /
      config:
        name: SFTEndpoint
        type: sftp
        parameters: {"host":"myhost.com.au",
                     "user": "myuser",
                     "pass": "",
                     "key-pem": -----BEGIN RSA PRIVATE KEY-----\nMaMbaIXtE\n0gAMbMbaSsd\nMbaass\n-----END RSA PRIVATE KEY-----}
```
`key-pem` can be generated by running the command: `awk '{printf "%s\\n", $0}' < ~/.ssh/id_rsa`

Alternatively, one can specifiy the location of the key file by using `key_file`.

Note that the public key must be put in the `authorized_keys` on the end point.

#### S3 Endpoint

```
endpoints:
  - name: dlm-archive
    location: AWS
    storage_type: objectstore
    interface: s3
    root_directory: /dlm-archive
    storage_phase: SOLID
    config:
      name: dlm-archive
      type: s3
      parameters: {"access_key_id": "access key",
                    "provider": "AWS",
                    "secret_access_key": "secret key",
                    "region": ap-southeast-2,
                    "location_constraint": ap-southeast-2}
```


## API Gateway

To install the OAuth API gateway:

  * Set `gateway.enabled` = `true`
  * Set `image` to the registry path of the container image.
  * Set `version` to the container image version.
  * Set `gateway.secret.name` to the name of the k8 secret (see below).

Create a k8 secret with the following Entra configuration items obtained by SKAO IT:

  * `PROVIDER` = `ENTRA`
  * `TENANT_ID` = `<Tenant ID>`
  * `CLIENT_ID` = `<Client ID>`
  * `CLIENT_CRED` = `<Client credential>`

Both `gateway.enabled` must be set `true` and `gateway.secret.name` has to be supplied for the gateway pod to be deployed.

## Benchmark

To run the benchmarking pod:

  * Set `benchmark.enabled` = `true`
  * Set `benchmark.name` = `register` or `migrate`
  * Set `benchmark.config.host` = hostname of the DLM gateway
  * Set `benchmark.config.token` = auth token
  * If `benchmark.name` = `migrate`:
    * `benchmark.config.sourceFile` = name of the migration yaml config file (must be created in the directory `charts/ska-dlm/benchmark`)
    * `benchmark.config.mountPath` = location in the pod the migration yaml config file will be copied

1) Setup port forwarding on the benchmark pod to port: `8089`
2) In a browser, navigate to `http://localhost:8089`. Now you should see a Locust GUI.
3) Click START

For details on the benchmark configuration, see the [documentation](../../scripts/README.md).

## Schema changes by release

### Working version

Note: The v1.1.2 directory holds the code required to migrate the database *from* 1.1.2 to the *next* release.

**Changes**:
* `data_item.metadata` column changed from `json` to `jsonb`

## Test Deployment

### Minikube Setup

* Start minikube (this is what was used during development but have confirmed other smaller values work)
  ```sh
  minikube start --disk-size 64g --cpus=6 --memory=16384
  ```

* If not already done, you will need to enable the ingress plugin:
  ```sh
  minikube addons enable ingress
  ```

* Add the Helm repositories required by `Chart.yaml`:
  ```sh
  helm repo add <name> <url>
  helm repo update
  ```

* From the root directory of this repository, download the Helm dependencies and initialise the database:
  ```sh
  make k8s-dep-build
  ```

- Depending on you system you may also need to run `minikube tunnel` in a separate terminal (notably [M1 Macs](https://github.com/kubernetes/minikube/issues/13510)). In this case, you can access ingress services via `localhost` instead of `minikube ip`.


### pgweb (optional)

Web IDE access to Postgres can be enabled by deploying pgweb in the cluster by adding `--set pgweb.enabled=true` to `K8S_CHART_PARAMS` in the project `Makefile`, or by setting `pgweb.enabled=true` in `values.yaml`. Once deployed, the pgweb interface can be accessed by port-forwarding the pgweb service or pod. For example, when using k9s, select the ``pgweb`` pod and press ``Shift+F`` to forward the default port (``8081``). Then open a browser and navigate to ``http://localhost:8081/``.
Log in using the appropriate database credentials. If you deployed a local Postgres instance, these correspond to the values defined under ``postgresql.auth`` in your ``values.yaml`` file.

With public network access to the development k8s cluster:

* navigate a browser to `http://<minikube ip>/pgweb/` (or with minikube tunneling, `http://localhost/pgweb/`)
* Select the scheme option
* Enter the URL `postgres://ska_dlm_admin:password@<helm-release>-postgresql.<host>:<port>/ska_dlm?sslmode=disable`.
Example of `<host>` on the DP cluster: *dp-shared.svc.cluster.local*

### Running Helm Chart Tests

#### k8s tests

Run the following to test against the running test deployment:
```sh
make k8s-install-chart
make k8s-test
```

Alternatively, installing, testing and uninstalling can be performed manually by running the following respective commands:

```sh
make k8s-install-chart
make k8s-do-test
make k8s-uninstall-chart
```

## Cluster Deployment

To deploy in a cluster k8s environment, DevOps can:

* Select the Kubernetes environment via `export KUBECONFIG="path to kubeconfig"`
* Modify the `resources/<location>-values.yaml` file to override helm values
* Install the release using the following commands:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
make k8s-dep-build

KUBE_NAMESPACE=<prod-namespace> HELM_RELEASE=<prod-release-name> HELM_VALUES=resources/<values_file> K8S_SKIP_NAMESPACE=1 make k8s-install-chart
```

* Uninstall a previously deployed release using the following commands:

```bash
KUBE_NAMESPACE=<prod-namespace> HELM_RELEASE=<prod-release-name> HELM_VALUES=resources/<values_file> K8S_SKIP_NAMESPACE=1 make k8s-uninstall-chart
```
