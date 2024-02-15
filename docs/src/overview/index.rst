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

The MVP implementation structures the code accordingly into the following sub-modules:

  - data_item, setter and update functions for the data_item table
  - dlm_db, DB maintenance functions (currently empty)
  - dlm_ingest, data_item ingest and initialization functions
  - dlm_migration, migration and copy functions
  - dlm_request, query functions
  - dlm_storage, location and storage initialization, configuration and query functions as well as data_item payload deletion.

With exception of the dlm_migration and the dlm_storage modules these are currently implemented as API libraries and can be used through direct REST calls as well as by using the python functions. The dlm_migration and dlm_storage module in addition have daemons running. Mid-term also the dlm_ingest and dlm_request modules will have daemons running and exposing REST interfaces.

The data_item Module
--------------------
This module collects all the setter and updating functions related to the data_item table in a separate module to avoid cyclic imports.

The DLM DB
----------
The MVP implementation is built around the DB schema shown in the figure below. The DB also implements a number of triggers, functions and foreign key relationships with associated constraints to keep the content consistent. Many of the columns of the tables have default values and are not mandatory (at least for early operations).

The metadata in the DLM DB solely covers the needs of the data management. By design it does not directly include the product specific metadata. If required, such metadata will need to be defined and collected in separate, but closely related DBs. The link between the DLM meta-data and the product specific meta data is the OID and the item_name. The DLM allows for a plugin system to extract and synchronize such meta-data during ingest. For the MVP the DLM DB has been implemented in PostgreSQL, but we also have a schema for the Yugabyte DB. Unfortunately the Yugabyte schema is not exactly the same due to some limitations.

.. image:: ../_static/img/DLM_DB_ERD.jpg

The DLM DB REST Server
^^^^^^^^^^^^^^^^^^^^^^
On top of the DB we are running a postgREST server, which connects to the DB and exposes a very complete RESTful interface. This postgREST intermediate layer is not strictly required, but makes the internal implemenation very homogenous, since it is using HTTP based requests almost everywhere. If the overhead turns out to be prohibitive, we can replace those calls with direct SQL calls. 

The DLM Ingest Manager Module
-----------------------------
The MVP implementation of the DLM-IngestManager is a registration service for data_items and does not deal with the actual data directly. In the DLM design we introduce the DLM data_item. A DLM data_item is an entity consisting of the meta-data and the payload, which is the actual data. During ingest the DLM-IngestManager does not touch the payload (aka data product), but only a reference to it (uri column) is registered in the DLM DB. The ingest activity makes the payload visible to the DLM system and enables the DLM to manage the lifecycle. The ingest process also assigns the internal unique IDs (OID and UID) to the data_item and sets a number of other DLM properties, like the expiration times, the state and the phase. A typical ingest process consists of the following steps:

  #. Initialisation of the data_item using *init_data_item*
  #. Writing of the data payload independently from the DLM system using whatever is required by the application producing the data.
  #. Setting of the URI pointing to the payload using *set_uri*
  #. Setting of the READY state using *set_state*

Steps 1 and 2 are interchangeable since the writing is totally independent from the DLM system.

Functions exposed:
  - ingest_data_item, given an item_name, a path to a payload and a storage_id register a new data_item and transition to READY state. 
  - init_data_item, given an item_name and optionally additional meta-data items initialize a new data_item.

The DLM Storage Manager Module
------------------------------
This manager is implementing the storage manager logic. In the MVP the storage manager daemon is implementing the functionality to support the acceptance criteria of the feature:

  #. delete_data_item_payload, Delete expired data_item payloads and setting the state to DELETED.
  #. Produce a copy of newly ingested data_items to one more configured storage backend. This is using the copy_data_item function of the dlm_migration module.
  #. Stub for handling a phase change heuristic engine.
  #. Stub for handling capacity based data movements.

The storage manager exposes a number of storage related function and is also running a background daemon, (currently) polling the DB using some of the functions provided by the request manager module in intervalls to retrieve lists of expired and newly ingested data_items, respectively and then use the delete and copy functions to act accordingly. The future implementations of the phase change and capacity engines will use the same functions as well to free up space on storage volumes running low in capacity, while still making sure that the required persistence level (phase) is maintained. In addition to the daemon functionality the storage manager module also exposes some of its internal functions. 

The DLM Migration Manager Module
--------------------------------
This manager is also a daemon, but we have chosen to use rclone running in server mode to provide this functionality. However, the DLM system allows to plugin other migration services as well. It is also possible to use multiple ones to cover specific requirements for certain storage backends. rclone is extremely versatile and will hopefully cover our needs for the most part. Whether it is performant enough to copy/move many PB of data across the globe has to be verified. In addition the module exposes two functions:

  - copy_data_item, the high level function to copy a data_item from one storage volume to another. This function integrates all the required lower level function calls and checks.
  - rclone_copy, the lowest level copy function, directly calling the rclone server. In future versions this function will not be exposed directly anymore.

The DLM Request Manager Module
------------------------------
The MVP implementation of this manager is limited to a number of convenience functions focusing on the required DB queries for the other DLM managers rather than any external users or systems. Eventually this will expose a web-based request handling and packaging system to support users or other systems requesting data to be delivered to their chosen endpoints. The currently exposed functions include:

  - query_data_item, generic function to query the data_item table.
  - query_exists, checks for the existence of a data_item identified by an item_name, OID or UID.
  - query_exists_and_ready, same as above, but only returns data_items if they are in READY state.
  - query_expired, returns all expired data_items given a datetime. 
  - query_item_storage, returns a list of all storage volumes containing a copy of a data_item identified by an item_name, OID or UID.

