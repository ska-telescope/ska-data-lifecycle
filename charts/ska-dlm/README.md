# SKA Data Lifecycle Management Chart

*This is a work in progress*

This chart currently installs PostgREST, and optionally Postgres via the bitnami chart.

The main options of interest are:

 * `postgresql.enabled`: if enabled, PostgreSQL is installed, otherwise an external installation will be necessary.
 * `postgresql.initialise`: if enabled, the DLM tables will be created automatically in the database.
 * `postgresql.primary.persistence.enabled`: if enabled, PostgreSQL will persist data between executions, otherwise it will start from scratch each time.


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

- Depending on you system you may also need to run `minikube tunnel` in a separate terminal(notably [M1 Macs](https://github.com/kubernetes/minikube/issues/13510)). In this case, you can access ingress services via `localhost` instead of `minikube ip`.


### pgweb (optional)

Web IDE access to Postgres can be enabled by deploying pgweb in the cluster by adding `--set pgweb.enabled=true` to `K8S_CHART_PARAMS` in the project `Makefile`.

With public network access to the development k8s cluster:

* navigate a browser to `http://<minikube ip>/pgweb/` (or with minikube tunneling, `http://localhost/pgweb/`)
* Select the scheme option
* Enter the URL `postgres://ska_dlm_admin:password@test-ska-dlm-postgresql.ska-dlm.svc.cluster.local/ska_dlm?sslmode=disable`

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
* Modify the `resources/initialized-dlm.yaml` file to override helm values
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