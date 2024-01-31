# Charts is a work in progress.

This needs to be tied up into the Makefile but documenting full manual process here first.

Currently the official PostgreSQL image is being used. The bitnami release of PostgreSQL was reviewed
as it already contains a feature rich chart, values and templates. This ended up overly complicating
the basic setup needed at this time though.

# For current setup

- Start minikube (this is what was used during development)

`minikube start --disk-size 64g --cpus=6 --memory=16384`

- Use docker within minkube environemnt

`eval $(minikube docker-env)`

- Start the Postgres pod using helm

`helm install dlm-psql charts/ska-dlm/`

- Confirm pod has started plus confirm its name for use in following kubectl command

`kubectl get pod`

- Initialise the PostgreSQL DB (would be nice to do this with helm above)

`kubectl exec --stdin --tty ska-dlm-postgres-0 -- psql -U postgres -h localhost -p 5432 < setup/DB/ska_dlm_meta.sql`

