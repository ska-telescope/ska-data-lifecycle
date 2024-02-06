# Charts is a work in progress.

This needs to be tied up into the Makefile but documenting full manual process here first.

Currently the official PostgreSQL image is being used. The bitnami release of PostgreSQL was reviewed
as it already contains a feature rich chart, values and templates. This ended up overly complicating
the basic setup needed at this time though.

# For current setup

- Start minikube (this is what was used during development but have confirmed other smaller values work)

`minikube start --disk-size 64g --cpus=6 --memory=16384`

- Use docker within minkube environemnt

`eval $(minikube docker-env)`

- Start the minikube tunnel to get the node IP address to connect to postgrest
- NOTE: This will not return so you will need a new window or run this in the background

`minikube tunnel --cleanup`

- Start the Postgres pod using helm, includes postgrest

`make helm-start-services`

- To shutdown/uninstall/remove the services

`make helm-stop-services`