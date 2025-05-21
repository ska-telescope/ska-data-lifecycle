# SKA Data Lifecycle Management Chart

This chart installs the DLM services, including PostgREST and, optionally, a PostgreSQL instance via the Bitnami chart.

The main configuration options are:

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

Database migrations are executed by Kubernetes Job resources as part of the Helm deployment process. There are two types of migrations:

**1. Base Migrations (Initial Schema Creation)**
To install the base DLM schema from scratch:

* Set `database.migration.enabled` = `true`
* Set `database.migration.base.baseInstall` = `true`

This will run the SQL scripts located under `charts/ska-dlm/initdb-scripts/`. Use this option when deploying into a fresh database with no existing schema.

**2. Patch Migrations (Schema Updates Between Releases)**
To apply schema changes introduced after the initial deployment:

* Set `database.migration.enabled` = `true`
* Set `database.migration.patch.patchInstall` = `true`.
* Set `database.migration.patch.patchVersion` to the release version (e.g., v1.1.2).

Patch SQL scripts are located at `charts/ska-dlm/patches/<version>/`. They are mounted into the migration pod at `/etc/sql/patch/` and executed in deployment order. The following section provides a breakdown of all patch releases in version order.
Note: `database.migration.base.baseInstall` and `database.migration.patch.patchInstall` can **not** be true at the same time.

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

* Add the following additional repositories to helm:
  ```sh
  helm repo add bitnami https://charts.bitnami.com/bitnami
  helm repo add ectobit https://charts.ectobit.com
  ```

* Download the helm dependencies and initialise the database from the root directory of this repository
  ```sh
  make k8s-dep-build
  ```

  * The chart lock can be regenerated using `make k8s-dep-update`

- Depending on you system you may also need to run `minikube tunnel` in a separate terminal (notably [M1 Macs](https://github.com/kubernetes/minikube/issues/13510)). In this case, you can access ingress services via `localhost` instead of `minikube ip`.


### pgweb (optional)

Web IDE access to Postgres can be enabled by deploying pgweb in the cluster by adding `--set pgweb.enabled=true` to `K8S_CHART_PARAMS` in the project `Makefile`, or by setting `pgweb.enabled=true` in `values.yaml`. Once deployed, you can access the interface by port-forwarding to the pgweb service.

With public network access to the development k8s cluster:

* navigate a browser to `http://<minikube ip>/pgweb/` (or with minikube tunneling, `http://localhost/pgweb/`)
* Select the scheme option
* Enter the URL `postgres://ska_dlm_admin:password@<helm-release>-postgresql.<host>:<port>/ska_dlm?sslmode=disable`
Example of <host> on the DP cluster: *dp-shared.svc.cluster.local*

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