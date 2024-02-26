# ska-data-lifecycle

## Introduction

The SKA data lifecycle management system (DLM) is designed to manage all intermediate and final data products of the SKA. Data products in the context of the DLM can be any digital asset from any subsystem, which needs to be persisted for a certain amount of time and made resilient against loss to a certain degree. The system will enable the implementation of the FAIR principles for SKA data products. Findability is supported by high and low level search interfaces, Accessibility by providing access to the products through standard methods, Interoperability by ensuring that the product descriptions are adhering to IVOA or other applicable standards and Reusability by maintaining the product quality, storage infrastructure and access over the whole lifetime of the products.

The DLM is designed as a service oriented system sitting on-top of a database. The external interfaces and APIs are based on the REST paradigm. The deployed system will need to be highly available and dependable, since the whole observatory and all its internal and external users will eventually depend on the DLM functioning properly. The number and frequency of transactions as well as the total data volume managed by the DLM will be very significant and thus the system will need to consider scalability as one of the main drivers for the implementation.

The current design consists of five services and this repository is organised accordingly:

- Database management service (DLMdb)
- Ingest management service (DLMingest)
- Request management service (DLMrequest)
- Storage management service (DLMstorage)
- Migration management service (DLMmigration)

## Installation
The repository contains helm charts to install the services, including the DB. However, the DLM in operations is supposed to run continuously and use SKAO wide services like a HA DB service as well as the authentication system.

## Startup as a test environment
To run the tests you will need to install [minikube](https://minikube.sigs.k8s.io/docs/), then start it and enable the ingress plugin:

``` bash
minikube start
minikube addons enable ingress
```

Then spin up the DLM environment, making sure to download helm dependencies and initialise the database:
``` bash
make k8s-namespace
make update-chart-dependencies
make install-and-init-dlm
```

On some systems you will also need to start `minikube tunnel` in separate terminal. The most notable case of this is M1 Macs (see [here](https://github.com/kubernetes/minikube/issues/13510) for more details), though there may be others. It is unknown if Intel Macs need this step (if you are running one please test it and update these docs!).

Finally you are ready to run the tests! Just execute `make python-test` and the tests will run against the running deployment.

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

### Test:

from the ska-data-lifecycle directory, run `pytest`

_This will populate the data_item table in the GUI_

## Shutdown
To take down the DLM retaining the data in the database (i.e. the persistent volume claim) run `make uninstall-dlm`. You can then bring it back up using `make install-dlm`. To delete everything, including all data, run `make k8s-delete-namespace`.