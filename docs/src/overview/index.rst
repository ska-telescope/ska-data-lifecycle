SKA DLM Overview
================
As outlined in the design, the DLM consists of five main services (managers):

  - DLM Ingest Manager
  - DLM Storage Manager
  - DLM Migration Manager
  - DLM Request Manager
  - DLM DB

These managers are bound together by a 'hidden' service, which is the DLM database. In operations, the DB engine is assumed to be provided, maintained and operated by other SKAO teams (and trains), but for the MVP we will start an engine locally. As a system the first thing which has to be up and running is the DLM DB. In operations this will require a HA DB setup and the load on this DB will be quite substantial. Actual numbers are dependent on the kind of data products from all over the organisation, which will eventually be managed by the DLM. There is now a process in place to collect such information.

The DLM is designed to accept arbitrary types and categories of data. It also allows to register and track relationships between data items. The most important features are centred around the management of the lifecycle and resilience of data items as well as the distribution over and across multiple storage volumes offering heterogenous performance and interface features. The MVP initially targets posix based file systems as well as S3 storage. The end-user (system) does not need to know any of the details of these storage systems or even their existence. This separation will also allow the operators to add new types of systems and remove retired or broken ones. Such functionality is foreseen and reflected by the DLM DB schema, but the functionality is not implemented in the MVP. The MVP does implement pieces of each of the services mentioned above, but mostly only to the degree to fullfill the requirements of the MVP.

At some stage in the future we may decide to split these services into separate repositories, but to get started everything is in one place. Also, the DLMdb service is not intended to be used in an operational deployment, but the DLM system will be a client of the observatory wide DB setup. The DLMingest and DLMrequest services are the main input and output services, respectively exposed to other subsystems and users. This will require APIs for subsystems and at least administrator and operator level user interfaces. Apart from the future Request Manager interface, end-users are not expected to access or use the DLM directly.

Please also refer to the DLM design description: https://confluence.skatelescope.org/x/rCYLDw

The DLM DB
----------
The MVP implementation is built around the DB schema shown below. The DB also implements a number of triggers, functions and foreign key relationships with associated constraints to keep the content consistent. Many of the columns of the tables have default values and are not mandatory (at least for early operations).

The metadata in the DLM DB solely covers the needs of the data management. By design it does not directly include the product specific metadata. If required, such metadata will need to be defined and collected in separate, but closely related DBs. The link between the DLM meta-data and the product specific meta data is the OID and the item_name. The DLM allows for a plugin system to extract and synchronize such meta-data during ingest. For the MVP the DLM DB has been implemented in PostgreSQL, but we also have a schema for the Yugabyte DB. Unfortunately the Yugabyte schema is not exactly the same due to some limitations.

.. image:: ../_static/img/DLM_DB_ERD.jpg

The DLM DB REST Server
----------------------
On top of the DB we are running a postgREST server, which connects to the DB and exposes a very complete RESTful interface. This postgREST intermediate layer is not strictly required, but makes the internal implemenation very homogenous, since it is using HTTP based requests almost everywhere. If the overhead turns out to be prohibitive, we can replace those calls with direct SQL calls. 

The DLM Ingest Manager
----------------------
The MVP implementation of the DLM-IngestManager is a registration service and does not deal with the actual data directly. In the DLM design we introduce the DLM data_item. A DLM data_item is an entity consisting of the meta-data and the payload, which is the actual data. During ingest the DLM-IngestManager does not touch the payload (aka data product), but only a reference to it (uri column) is registered in the DLM DB. The ingest activity makes the payload visible to the DLM system and enables the DLM to manage the lifecycle. The ingest process also assigns the internal unique IDs (OID and UID) to the data_item and sets a number of other DLM properties, like the expiration times, the state and the phase. A typical ingest process consists of the following steps:

  #. Initialisation of the data_item using *init_data_item*
  #. Writing of the data payload independently from the DLM system using whatever is required by the application producing the data.
  #. Setting of the URI pointing to the payload using *set_uri*
  #. Setting of the READY state using *set_state*

Steps 1 and 2 are interchangeable since the writing is totally independent from the DLM system.

The DLM Storage Manager
-----------------------
This manager is implementing the storage manager logic. In the MVP the storage manager daemon is implementing the bare minimum functionality to support the requested functionality:

  #. Delete expired data_item payloads and setting the state to DELETED.
  #. Produce a copy of newly ingested data_items to one more configured storage backend.
  #. Stub for handling a phase change heuristic engine.
  #. Stub for handling capacity based data movements.

The storage manager is mostly a background daemon, (currently) polling the DB using some of the functions provided by the request manager module in intervalls to retrieve lists of expired and newly ingested data_items, respectively and then use the delete and copy functions to act accordingly. The future implementations of the phase change and capacity engines will use the same functions as well to free up space on storage volumes running low in capacity, while still making sure that the required persistence level (phase) is maintained. In addition to the daemon functionality the storage manager module also exposes some of its internal functions. 

The DLM Migration Manager
-------------------------
This manager is also a daemon, but we have chosen to use rclone running in server mode to provide this functionality. However, the DLM system allows to plugin other migration services as well. It is also possible to use multiple ones to cover specific requirements for certain storage backends. rclone is extremely versatile and will hopefully cover our needs for the most part. Whether it is performant enough to copy/move many PB of data across the globe has to be verified.

The DLM Request Manager
-----------------------
The MVP implementation of this manager is limited to a number of convenience functions focusing on the required DB queries for the other DLM managers rather than any external users or systems. Eventually this will expose a web-based request handling and packaging system to support users or other systems requesting data to be delivered to their chosen endpoints. One stub supporting this does exist already in a function allowing to register a new storage location and configuration for rclone. 
