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

At some stage in the future we may decide to split these services into separate repositories, but to get started everything is in one place. Also, the DLMdb service is not intended to be used in an operational deployment, but the DLM system will be a client of the observatory wide DB setup. The DLMingest and DLMrequest services are the main input and output services, respectively exposed to other subsystems and users. This will require APIs for subsystems and at least administrator and operator level user interfaces. End-users are not expected to access or use the DLM directly.

Please also refer to the DLM design description: https://confluence.skatelescope.org/x/rCYLDw

## Installation
TBD

## Startup as a test environment
### Start the DB:

`docker run --rm --name ska-dlm -p 5433:5432 -e POSTGRES_PASSWORD=mysecretpassword -d postgres`

### Setup the ska-dlm DB:
From inside the ska-data-lifecycle repo directory run:

`psql -U postgres -h localhost -p 5433 -f setup/DB/ska_dlm_meta.sql`

### Start the postgREST layer:
After the installation of postgREST the command `postgrest` should be available on the PATH. In that case you can run:

`postgrest setup/postgREST/postgREST.conf`

from inside the ska-data-lifecycle repo directory.\
_This will run in the terminal thus to start PostGUI you need to use another terminal._

### Create or replace the file src/data/config.json with the following:
```json
{
  "databases": [
    {
      "title": "SKA-DLM",
      "url": "http://localhost:3001",
      "publicDbAcessType": "read",
      "foreignKeySearch": true,
      "primaryKeyFunction": true,
      "regexSupport": false
    }
  ],
  "logoUrl": "https://jira.skatelescope.org/s/nfi585/940012/168qw7/_/jira-logo-scaled.png",
  "seq_column_names": [
    "alignment_sequence",
    "nucleotide_sequence",
    "aminoacid_sequence",
    "nucleotide_seq",
    "amino_acid_seq",
    "nuc_seq",
    "aa_seq",
    "dna_seq",
    "protein_seq",
    "prot_seq",
    "n_seq",
    "p_seq",
    "a_seq",
    "seq",
    "sequence"
  ],
  "errorMsg": "ERROR"
}
```

### Create a file in the main directory called .secrets.yaml with the following content:
`db_password: "mysecretpassword"`

### Create the PostGUI directory:
`git clone https://github.com/priyank-purohit/PostGUI`

### Start the PostGUI:
From inside the PostGUI repository directory run (for Unix):

`npm install`\
`export NODE_OPTIONS=--openssl-legacy-provider`\
`npm start`

_This will also run inside the terminal._

### Test:

from the ska-data-lifecycle directory, run `pytest`

_This will populate the data_item table in the GUI_

## Shutdown
Just kill the processes inside the PostGUI and postgREST terminals and shut down the DB using the command:

`docker stop ska-dlm`

**_Note: Since we had specified `--rm` on the docker command line to start the DB this will also delete the container and thus all DB setup and data will be gone as well._**