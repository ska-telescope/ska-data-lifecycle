Local Development
=================

Interact with DLM by the way of local Docker deployment, using python methods or the CLI interface.
From within your DLM directory, start the DLM services first, e.g., by running::

  docker compose -f tests/testrunner.docker-compose.yaml -p dlm-test-services build
  docker compose -f tests/testrunner.docker-compose.yaml -p dlm-test-services up -d


The following sections describe how to **register** and **migrate** a data item from within a DLM server without the RESTful interface. This can be performed either on a developer machine after installing the ``ska-data-lifecycle`` package, or via a remote session to a DLM server instance.

.. _local-development-cli:

Command Line Interface
------------------------

Set up a Location:

.. code-block:: bash

  # Check if the location MyLocation already exists in the database
  ska-dlm storage query-location --location-name MyLocation
  # Initialise location (if it doesn't already exist)
  ska-dlm storage init-location MyLocation local-dev

.. tip::

  The `pgAdmin application <https://www.pgadmin.org/>`_ provides an easy way to view your database.

Set up a storage:

.. code-block:: bash

  # Check if the storage MyDisk already exists
  ska-dlm storage query-storage --storage-name MyDisk
  # If not, initialise a storage with root directory "/"
  ska-dlm storage init-storage MyDisk filesystem "/" posix --location-name MyLocation

Set up a storage configuration:

.. code-block:: bash

  # Check if a storage config for MyDisk is already known to DLM
  ska-dlm storage get-storage-config --storage-name MyDisk
  # If not, create a storage config for MyDisk. The default config_type is rclone.
  ska-dlm storage create-storage-config \
    '{"name":"MyDisk", "type":"alias", "root_path":"/", "parameters":{"remote": "/"}}' \
    --storage-id '<the storage id received above>'

Register a data item:

.. code-block:: bash

  # Register an existing data item inside the rclone container (e.g., /etc/os-release)
  ska-dlm ingest register-data-item test_item_name etc/os-release --storage-name MyDisk \
  --metadata='{"execution_block":"eb-m001-20191031-12345"}'

Query for a data item:

.. code-block:: bash

  # Query for data items called "test_item_name"
  ska-dlm data-item query-data-item --item-name test_item_name

Migrate a data item:

.. code-block:: bash

  # Migrate an item from one storage to another
  # Register a second storage (same or different location)
  ska-dlm storage init-storage MyDisk2 filesystem "/" posix --location-name MyLocation

.. code-block:: bash

  # Supply a storage configuration for the second storage
  ska-dlm storage create-storage-config \
  '{"name":"MyDisk2", "root_path": "/", "type":"alias", "parameters":{"remote": "/"}}' \
  --storage-id '<the storage id received above>'

.. code-block:: bash

  # Copy your data item from MyDisk to MyDisk2
  ska-dlm migration copy-data-item --item-name test_item_name --destination-name MyDisk2 \
  --path /data/test_item

Query for the item again:

.. code-block:: bash

  # Query for all instances of "test_item_name"
  ska-dlm data-item query-data-item --item-name test_item_name

If you can't find the command you need, follow the help prompts:

.. code-block:: bash

  ska-dlm --help

.. _local-development-python-script:


Python module interface
------------------------

Set up a location:

.. code-block:: python

  from ska_dlm import dlm_storage, dlm_ingest, dlm_migration, dlm_request

  location_name = "MyLocation"
  location_type = "local-dev"

  # Check if the location 'MyLocation' is already known to DLM
  dlm_storage.query_location(location_name=location_name)
  # Initialise the location (if it doesn't already exist)
  location_id = dlm_storage.init_location(location_name, location_type)

Set up a storage:

.. code-block:: python

  # Check if the storage 'MyDisk' is already known to DLM
  dlm_storage.query_storage(storage_name="MyDisk")
  # Initialise the storage (if it doesn't already exist)
  storage_id = dlm_storage.init_storage(
      storage_name="MyDisk",
      root_directory="/",
      location_id=location_id, # the location ID retrieved in the previous step
      storage_type="filesystem",
      storage_interface="posix",
      storage_capacity=100000000,
  )

Set up a Storage Configuration:

.. code-block:: python

  # Check if a storage configuration for 'MyDisk' already exists
  dlm_storage.get_storage_config(storage_name="MyDisk")
  # Supply a storage_config, if one doesn't already exist (default `config_type` is rclone)
  config = {"name": "MyDisk", "type": "alias", "root_path": "/", "parameters": {"remote": "/"}}
  config_id = dlm_storage.create_storage_config(storage_id=storage_id, config=config)

Register a data item:

.. code-block:: python

  # Register an existing data item inside the rclone container (e.g., /etc/os-release)
  uid = dlm_ingest.register_data_item(
      item_name="test_item",
      uri="/etc/os-release",
      storage_name="MyDisk",
      item_type="file",
      metadata={"execution_block": "eb-m001-20191031-12345"},
  )

Migrate a data item:

.. code-block:: python

  # Migrate an item from one storage to another
  # Register a second storage
  storage_id = dlm_storage.init_storage(
      storage_name="MyDisk2",
      root_directory="/",
      location_id=location_id, # can be the same location_id or a new location
      storage_type="filesystem",
      storage_interface="posix",
      storage_capacity=100000000,
  )
  # Supply a storage_config
  config = {"name": "MyDisk2", "type": "alias", "root_path": "/", "parameters": {"remote": "/"}}
  config_id = dlm_storage.create_storage_config(storage_id=storage_id, config=config)

  # Copy "test_item" from MyDisk to MyDisk2
  dlm_migration.copy_data_item("test_item", destination_name="MyDisk2", path="/data/test_item")

Query for the data item:

.. code-block:: python

  # Query for all instances of "test_item"
  dlm_request.query_data_item("test_item")


Remember to tear down the services::

  docker compose -f tests/testrunner.docker-compose.yaml -p dlm-test-services down

