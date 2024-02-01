SKA DLM Overview
==================================
As outlined in the design, the DLM consists of five main services (managers):

  - DLM Ingest Manager
  - DLM Storage Manager
  - DLM Migration Manager
  - DLM Request Manager
  - DLM DB

These managers are bound together by a 'hidden' service, which is the DLM database. In operations, the DB engine is assumed to be provided, maintained and operated by other SKAO teams (and trains), but for the MVP we will start an engine locally. As a system the first thing which has to be up and running is the DLM DB. In operations this will require a HA DB setup and the load on this DB will be quite substantial. Actual numbers are dependent on the kind of data products from all over the organisation, which will eventually be managed by the DLM. There is now a process in place to collect such information.

The DLM is designed to accept arbitrary types and categories of data. It also allows to register and track relationships between data items. The most important features are centred around the management of the lifecycle and resilience of data items as well as the distribution over and across multiple storage volumes offering heterogenous performance and interface features. The MVP initially targets posix based file systems as well as S3 storage. The end-user (system) does not need to know any of the details of these storage systems or even their existence. This separation will also allow the operators to add new types of systems and remove retired or broken ones. Such functionality is foreseen and reflected by the DLM DB schema, but the functionality is not implemented in the MVP. The MVP does implement pieces of each of the services mentioned above, but mostly only to the degree to fullfill the requirements of the MVP.

The DLM DB
----------
The MVP implementation is built around the DB schema shown below. The DB also implements a number of triggers, functions and foreign key relationships with associated constraints to keep the content consistent. Many of the columns of the tables have default values and are not mandatory (at least for early operations).

The metadata in the DLM DB solely covers the needs of the data management. By design it does not directly include the product specific metadata. If required, such metadata will need to be defined and collected in separate, but closely related DBs. The link between the DLM meta-data and the product specific meta data is the OID and the item_name. The DLM allows for a plugin system to extract and synchronize such meta-data during ingest. For the MVP the DLM DB has been implemented in PostgreSQL, but we also have a schema for the Yugabyte DB. Unfortunately the Yugabyte schema is not exactly the same due to some limitations.

.. image:: ../_static/img/DLM_DB_ERD.png

The DLM DB REST Server
----------------------
On top of the DB we are running a postgREST server, which connects to the DB and exposes a very complete RESTful interface. This postgREST intermediate layer is not strictly required, but makes the internal implemenation very homogenous, since it is using HTTP based requests almost evreywhere. If the overhead turns out to be prohibitive, we can replace those calls with direct SQL calls. 

The DLM Ingest Manager
----------------------
The MVP implementation of the ingest manager is a registration service and does not (initially) deal with the actual data directly. In the DLM design we distinguish between the data_item and the payload. The data_item is an entity consisting of the meta-data and the payload, which is the actual data. The payload is not actually touched by the DLM during ingest, but only a reference to it (uri column) is registered in the DLM DB. 