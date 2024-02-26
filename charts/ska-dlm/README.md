# SKA Data Lifecycle Management chart

*This is a work in progress*

This chart currently installs PostgREST, and optionally Postgres via the bitnami chart.

The main options of interest are:

 * `postgresql.enabled`: if enabled, PostgreSQL is installed, otherwise an external installation will be necessary.
 * `postgresql.initialise`: if enabled, the DLM tables will be created automatically in the database.
 * `postgresql.primary.persistence.enabled`: if enabled, PostgreSQL will persist data between executions, otherwise it will start from scratch each time.

## Running in Minikube

- Start minikube (this is what was used during development but have confirmed other smaller values work)

  `minikube start --disk-size 64g --cpus=6 --memory=16384`

- If not already done, you will need to enable the
  ingress plugin:

  `minikube addons enable ingress`

- Install a release of this chart.
  In this example the chart is being installed under the `test` namespace,
  the release is called `ska-dlm`.

  First get chart dependencies:

  `helm dependency update`

  From the top-level directory of this repository, create the namespace `test`
(if you do not already have it):

  `kubectl create namespace test`

  Finally, install the chart:

  `helm install -n test ska-dlm charts/ska-dlm`

- To uninstall the previously installed release
  (again, using the same names as in the previous example):

  `helm uninstall -n test ska-dlm`
