# SKA Data Lifecycle Management Chart

*This is a work in progress*

This chart currently installs PostgREST, and optionally Postgres via the bitnami chart.

The main options of interest are:

 * `postgresql.enabled`: if enabled, PostgreSQL is installed, otherwise an external installation will be necessary.
 * `postgresql.initialise`: if enabled, the DLM tables will be created automatically in the database.
 * `postgresql.primary.persistence.enabled`: if enabled, PostgreSQL will persist data between executions, otherwise it will start from scratch each time.


## Test Deployment

### Minikube Setup

- Start minikube (this is what was used during development but have confirmed other smaller values work)

  `minikube start --disk-size 64g --cpus=6 --memory=16384`

- If not already done, you will need to enable the ingress plugin:

  `minikube addons enable ingress`

- Add the additional repositories to helm:

  `helm repo add bitnami https://charts.bitnami.com/bitnami`

- Make sure to download helm dependencies and initialise the database ensuring you are in the root directory of this repository:

  `make k8s-dep-build`

- Depending on you system you may also need to run `minikube tunnel` in a separate terminal(notably [M1 Macs](https://github.com/kubernetes/minikube/issues/13510)). In this case, you can access ingress services via `localhost` instead of `minikube ip`.

### Optional
The DLM system is complete now, but in order to have a view into the DB you can run the nice PostGUI web interface, which talks to postgREST.

#### Clone the PostGUI into a directory on the same level as the `ska-data-lifecycle` one:
`git clone https://github.com/priyank-purohit/PostGUI`\
`cd PostGUI`

Replace the file src/data/config.json with the file `setup/postgrest/config.json`, replacing `$(minikube ip)` in the url with the result from your terminal, and `$(KUBE_NAMESPACE)` with the namespace you deployed to (by default in the Makefile: `ska-dlm`).

#### Start the PostGUI:
From inside the PostGUI repository directory run (for Unix):

`npm install`\
`export NODE_OPTIONS=--openssl-legacy-provider`\
`npm start`

_This will run interactively in the terminal._

### Running Helm Chart Tests

Run the following to test against the running test deployment:
```bash
make k8s-test
```

Alternatively, installing, testing and uninstalling can be performed manually by running the following respective commands:

```bash
make k8s-install-chart
make k8s-do-test
make k8s-uninstall-chart
```

## Production Deployment

A host can deploy to a production environment by setting up `KUBE_CONFIG` and using the following `helm` and `kubectl` commands from the repository root directory:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
make k8s-dep-build

KUBE_NAMESPACE=<prod-namespace> HELM_RELEASE=<prod-release> make k8s-install-chart
```

To uninstall a previously deployed release use:

```bash
KUBE_NAMESPACE=<prod-namespace> HELM_RELEASE=<prod-release> make k8s-uninstall-chart
```