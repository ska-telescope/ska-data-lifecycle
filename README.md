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
To run the tests just execute `make python-test`. This will startup all services, run the tests and shutdown everything again. For a more permanent setup follow the steps below. In future we may implement a make target just starting the services and keep them alive until shutdown.

### Start the DB:

`docker run --rm --name ska-dlm -p 5432:5432 -e POSTGRES_PASSWORD=mysecretpassword -d postgres`

### Setup the ska-dlm DB:
From inside the ska-data-lifecycle repo directory run:

`psql -U postgres -h localhost -p 5432 -f setup/DB/ska_dlm_meta.sql`

### Start the postgREST layer:
After the installation of postgREST the command `postgrest` should be available on the PATH. In that case you can run:

`postgrest setup/postgREST/postgREST.conf`

from inside the ska-data-lifecycle repo directory.\
_This will run interactively in the terminal._

### Create a file in the main directory called .secrets.yaml with the following content:
`db_password: "mysecretpassword"`

### Optional
The DLM system is complete now, but in order to have a view into the DB you can run the nice PostGUI web interface, which talks to postgREST.
#### Clone the PostGUI into a directory on the same level as the `ska-data-lifecycle` one:
`git clone https://github.com/priyank-purohit/PostGUI`\
`cd PostGUI`

Replace the file src/data/config.json with the file `ska-data-lifecycle/setup/postgrest/config.json`


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
Just kill the processes inside the PostGUI and postgREST terminals and shut down the DB using the command:

`docker stop ska-dlm`

**_Note: Since we had specified `--rm` on the docker command line to start the DB this will also delete the container and thus all DB setup and data will be gone as well._**