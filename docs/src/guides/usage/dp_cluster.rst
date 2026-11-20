External Storage
================

.. _dp-cluster:

DLM Client: Directory Watcher
------------------------------

Please refer to the `Directory Watcher guide <https://developer.skatelescope.org/projects/ska-dlm-client/en/latest/api/directory_watcher.html>`_ (*WIP*) on the dlm-client documentation.


DLM Client: ConfigDB Watcher
-----------------------------

Please refer to the `ConfigDB Watcher guide <https://developer.skatelescope.org/projects/ska-dlm-client/en/latest/api/configdb_watcher.html>`_ (*WIP*) on the dlm-client documentation.


REST API interface
------------------------

This section outlines the steps required to ingest and migrate data directly through the DLM Server, by using the SKA-DLM REST API interface.

1. Obtain an API token for authenticated access to the DLM API
2. Determine the location of the file(s) you wish to register, and register the location with DLM
3. Determine the storage where the file(s) are stored, and register the storage with DLM
4. Ensure the storage is accessible from DLM by supplying a configuring for your storage
5. Ingest the files into DLM one-by-one
6. Instruct DLM to migrate the newly ingested item to a secondary storage
7. Query for all copies of the data item

In the Python code below, we register an arbitrarily chosen file residing on an external storage, Acacia, located at the Pawsey Centre.
We make use of the DLM deployment on the DP platform, in the dp-dm namespace.

**1. Prepare token to be placed in the header of your REST calls**

* Open a browser and go to the ``/token_by_auth_flow`` endpoint on the DLM server URL.
* For example, for the DLM deployment on the DP cluster: ``https://sdhp.stfc.skao.int/dp-dm/dlm/token_by_auth_flow``.
* Log in with your credentials
* If successful, a token will be returned. Copy the token.

.. code-block:: python

   from requests import Session

   # this URL is for DLM deployment in the 'dp-dm' namespace on the DP test platform
   DLM_URL = "https://sdhp.stfc.skao.int/dp-dm/dlm"
   token = <your token>
   headers = {"Authorization": f"Bearer {token}"}
   session = Session()

**2. Check if your desired location (e.g., Pawsey) is already known to DLM**

.. code-block:: python

   # create location details
   location_name = "Pawsey"
   location_type = "low-integration"

   location = session.get(
       f"{DLM_URL}/storage/query_location",
       params={"location_name": location_name},
       headers=headers,
       timeout=60,
   )
   print(location.json())
   location_id = location.json()[0]["location_id"]  # if location exists, get the location id

If your desired location doesn't already exist, initialise it

.. code-block:: python

   loc_params = {
       "location_name": location_name,
       "location_type": location_type,
   }
   location = session.post(
       f"{DLM_URL}/storage/init_location", params=loc_params, headers=headers, timeout=60
   )
   print(location.json())
   location_id = location.json()  # get the location id

**3. Check if your desired storage (e.g., Acacia) is already known to DLM**

.. code-block:: python

   storage_params = {
       "storage_name": "Acacia",
       "location_id": location_id,
   }
   storage = session.get(
       f"{DLM_URL}/storage/query_storage", params=storage_params, headers=headers, timeout=60
   )
   print(storage.json())
   storage_id = storage.json()[0]["storage_id"]  # if the storage exists, get the storage id

If your storage is not listed, register a supported storage endpoint. The default ``config_type`` is ``rclone``.
For more information, refer to the `rclone configuration docs <https://rclone.org/docs/#configure>`_.

.. code-block:: python

   storage_params = {
       "storage_name": "Acacia",
       "root_directory": "ska-sdp",
       "location_id": location_id,
       "storage_type": "objectstore",
       "storage_interface": "s3",
       "storage_capacity": 100000000,
   }
   storage = session.post(
       f"{DLM_URL}/storage/init_storage",
       params=storage_params,
       headers=headers,
       timeout=60,
   )
   print(storage.json())
   storage_id = storage.json()  # get the storage_id

**4. Check what configurations for your storage are already known to DLM**

.. code-block:: python

   config = session.get(
       f"{DLM_URL}/storage/get_storage_config",
       params={"storage_id": storage_id},
       headers=headers,
       timeout=60,
   )
   print(config.json())

Supply a configuration for your storage, if one doesn't exist. The default ``config_type`` is ``rclone``.
For further details, refer to the `rclone configuration docs <https://rclone.org/docs/#configure>`_.

.. code-block:: python

   acacia_config = {
    "name": "myacacia",
    "type": "s3",
    "root_path": "/",
    "parameters": {
        "access_key_id": "<your-access-key-id>",
        "endpoint": "https://projects.pawsey.org.au",
        "provider": "Ceph",
        "secret_access_key": "<your-secret-access-key>",
       },
   }
   config = session.post(
       f"{DLM_URL}/storage/create_storage_config",
       params={"storage_id": storage_id},
       json=acacia_config,
       headers=headers,
       timeout=60,
   )
   print(config.json())

**5. Register a data item that exists on your storage**

.. code-block:: python

   item_params = {
       "item_name": "test_item",
       "uri": "rascil/1197634128-cal_avg32.ms.tar.xj",  # randomly chosen example file
       "storage_name": "Acacia",
       "storage_id": storage_id,
   }
   json_body = {"execution_block": "eb-m001-20191031-12345"}  # example metadata
   acacia_response = session.post(
       f"{DLM_URL}/ingest/register_data_item",
       params=item_params,
       json=json_body,
       headers=headers,
       timeout=60,
   )
   print(acacia_response.json())

**6. Trigger a migration to a second storage.**

If your destination storage isn't known to DLM, first initialise it (using the method above). Then initiate a migration:

.. warning::

   The worker first copies into a migration-specific staging path and verifies
   the bytes against a source snapshot before publishing. Existing destination
   paths are not overwritten: the migration fails and leaves the staged data
   for operator inspection if the final path already exists. The source must
   remain immutable through verification; later external changes are not
   prevented. Database transactions do not make storage operations atomic or
   guarantee exactly-once execution.

   A failed or interrupted copy can leave partial destination data. The worker
   does not delete it automatically because it cannot establish ownership.
   Migrations marked ``reconciliation_required`` are not automatically
   retried: stop any old worker and inspect the destination before manually
   reconciling the record. For legacy jobs from the old Rclone daemon, stop
   that daemon before inspecting the payload and manually retrying.

   S3 migrations may opt into indefinite automatic full-copy retries by setting
   the destination Rclone S3 configuration parameter
   ``leave_parts_on_error`` to ``true``. Retries reuse the same staging object
   and stop if the source bytes have changed. Rclone 1.75.1 does not resume
   previously uploaded multipart parts on a new operation, so retries restart
   the object transfer; preserved multipart parts can incur storage charges.
   Configure an S3 lifecycle rule to abort incomplete multipart uploads. SFTP
   partial uploads are not retried automatically. Stop/scale down the
   ``dlm_rclone_worker`` to pause retries; it resumes them after restart. To
   keep a migration stopped across restarts, set
   ``job_status.reconciliation_required`` to ``true`` for that migration.

.. code-block:: python

   migration_params = {
       "item_name": "test_item",
       "destination_name": <dest_storage>,
       "path": <dest_path>,
   }
   migration_response = session.post(
       f"{DLM_URL}/migration/copy_data_item",
       params=migration_params,
       headers=headers,
       timeout=60,
   )
   print(migration_response.json())

**7. Query for all copies of the data item**

.. code-block:: python

   response = session.get(
       f"{DLM_URL}/request/query_data_item",
       params={"item_name": "test_item"},
       headers=headers,
       timeout=60,
   )
   print(response.json())

