# SKA Data Lifecycle Management chart

*This is a work in progress*

This chart currently installs PostgREST, and optionally Postgres via the bitnami chart.

The main options of interest are:

 * `postgresql.enabled`: if enabled, PostgreSQL is installed, otherwise an external installation will be necessary.
 * `postgresql.initialise`: if enabled, the DLM tables will be created automatically in the database.
 * `postgresql.primary.persistence.enabled`: if enabled, PostgreSQL will persist data between executions, otherwise it will start from scratch each time.

## Running in Minikube

Ensuring you are in the root directory of the repository:

- Start minikube (this is what was used during development but have confirmed other smaller values work)

  `minikube start --disk-size 64g --cpus=6 --memory=16384`

- If not already done, you will need to enable the
  ingress plugin:

  `minikube addons enable ingress`

- Depending on you system you may also need to run `minikube tunnel`
  in a separate terminal
  (notably [M1 Macs](https://github.com/kubernetes/minikube/issues/13510)).
  In this case, you can access ingress services via `localhost` instead
  of `minikube ip`.

- Install a release of this chart.
  In this example the chart is being installed under the `test` namespace,
  the release is called `ska-dlm`.

  First, make a note of the chart directory. e.g. `CHART="charts/ska-dlm"`.

  Then get chart dependencies:

  `helm dependency update "$CHART"`

  From the top-level directory of this repository, create the namespace `test`
  (if you do not already have it):

  `kubectl create namespace test`

  Finally, install the chart:

  `helm install -n test ska-dlm "$CHART"`

- To uninstall the previously installed release
  (again, using the same names as in the previous example):

  `helm uninstall -n test ska-dlm`
