Helm Install
=============

*WIP*

For help on installing ska-dlm *client*, please refer to the `dlm-client documentation <https://developer.skatelescope.org/projects/ska-dlm-client/en/latest/>`_.

To install the DLM server services on a Kubernetes cluster, e.g., the DP cluster, start by cloning the repository (if not already present):

.. code-block:: bash

    git clone --recurse-submodules https://gitlab.com/ska-telescope/ska-data-lifecycle.git

Retrieve the available release tags and check out the desired release:

.. code-block:: bash

    cd ska-data-lifecycle
    git fetch --tags
    git tag --list
    git checkout <release-tag>

Configure the Helm chart
-------------------------

Configure the ``values.yaml`` file to match your environment and deployment requirements.

**The main configuration options are:**

* ``global.ingress.enabled``: If set to false, no Ingress resources will be created, meaning external access to services like pgweb and PostgREST will be unavailable. Set to true to expose these services outside the cluster.
* ``postgresql.enabled``: If true, a PostgreSQL instance will be deployed via the Bitnami chart. Otherwise, an external PostgreSQL service is assumed.
* ``postgresql.primary.persistence.enabled``: If enabled, PostgreSQL will persist data between executions; otherwise it will start from scratch each time.
* ``database.migration.enabled``: If true, the DLM tables will be created automatically in the database. Must be true for any base or patch migration to run. See :ref:`database-migrations` for more information.
* ``database.migration.image``: The Docker image used for executing SQL migration jobs (default: ``postgres``).
* ``database.migration.version``: Version tag of the migration image (default: 17.4).

Authentication
---------------

DB authentication details for PostgREST are stored in a Kubernetes ``Secret``.

- ``create``: Whether to create a secret.

  * If unset, an existing one must be provided via ``name``.
  * If set, the ``Secret`` is created from Vault contents at ``vault.{mount,path,type}``.

- In both cases, the ``Secret`` must provide the following keys: ``PGHOST``, ``PGUSER``, ``PGPASSWORD`` and ``PGDATABASE``.


Shared volume
--------------

In order for data to be shared between pods, ensure that the PVC ``global.sharedpvc`` is instantiated.
RClone generates an SSH key pair which it shares with the Storage Manager via ``global.sharedpvc`` so it can be distributed to storage endpoints via the REST endpoint ``get_ssh_public_key``.

Rclone Helm Chart ``secret`` values
------------------------------------

* ``secret.enabled``: If ``true``, enable rclone secrets.
* ``secret.name``: Name of an existing secret created externally. Used only if ``secret.vault.enabled`` is ``false`` and the value is not empty.
* ``secret.mountPoint``: Secrets mount point in the rclone pod.
* ``secret.ssl_cert_name``: Name of the SSL cert secret located in ``mountPoint``. If empty, SSL will be disabled.
* ``secret.ssl_key_name``: Name of the SSL key secret located in ``mountPoint``. If empty, SSL will be disabled.
* ``secret.vault``:

   * ``enabled``: If ``true``, use Vault to populate the secret. ``secret.enabled`` must also be ``true``.
   * ``mount``: Vault root.
   * ``type``: Vault engine type (defaults to ``kv-v2``).
   * ``path``: Vault path.


Pgweb
------

Web IDE access to Postgres can be enabled by deploying pgweb in the cluster by setting ``pgweb.enabled`` : ``true``. Once deployed, you can access the interface by port-forwarding to the pgweb service.


.. _database-migrations:

Database Migrations
---------------------

Database migrations are executed by Kubernetes Job resources as part of the Helm deployment process. There are two types of migrations:

**Base Migrations (Initial Schema Creation)**

To install the base DLM schema from scratch:

- Set ``database.migration.enabled`` : ``true``.
- Set ``database.migration.base.baseInstall`` : ``true``.

This runs the SQL scripts located under ``charts/ska-dlm/initdb-scripts/``. Use this option when deploying into a fresh database with no existing schema.

**Patch Migrations (Schema Updates Between Releases)**

To apply schema changes introduced after the initial deployment:

- Set ``database.migration.enabled`` : ``true``.
- Set ``database.migration.patch.patchInstall`` : ``false`` for now, as the database migration process is still being formalised (see `Managing database schema changes <https://confluence.skatelescope.org/display/SE/Managing+database+schema+changes>`_).
- Set ``database.migration.patch.patchVersion`` to the desired release version (e.g., ``v1.1.2``).

Patch SQL scripts are located at ``charts/ska-dlm/patches/<version>/``. They are mounted into the migration pod at ``/etc/sql/patch/`` and executed in alphabetical order.
Note: ``database.migration.base.baseInstall`` and ``database.migration.patch.patchInstall`` cannot both be ``true`` at the same time.

Storage Manager
----------------

There is an option to create multiple locations when the storage manager starts by adding:

``locations``:

  - ``name``: name of the location (free text – no enum or lookup constraints)
  - ``type``: type of storage (``local-dev``, ``low-integration``, ``mid-integration``, ``low-operations``, ``mid-operations``)
  - ``country``: country where storage is located (``AU``, ``AZ``, ``UK``)
  - ``city``: city where the storage is located
  - ``facility``: specific location (``SRC``, ``STFC``, ``AWS``, ``Google``, ``Pawsey Centre``, ``external``, ``local``)

  - ``name``: ...
  - ``type``: ...

There is also an option to create multiple **storage** endpoints when the storage manager starts by adding the following list of named values:


``endpoints``:

  - ``name``: storage name (free text – no enum or lookup constraints)
  - ``location``: name of existing location endpoint
  - ``storage_type``: type of storage endpoint (``filesystem``, ``objectstore``, ``tape``)
  - ``interface``: storage interface (``posix``, ``s3``, ``sftp``, ``https``)
  - ``root_directory``: root directory of mount point.
  - ``config``:

      - ``name``: rclone storage name
      - ``type``: rclone storage type i.e. (``s3``, ``alias``, ...)
      - ``parameters``: rclone parameters as a json dictionary

  - ``name``: ...
  - ``location``: ...


* Set ``storage.endpointSecretName`` to the name of the predefined k8 secret. The secret can contain the rclone secrets for a named storage endpoint. The ``config.parameters`` value for an endpoint will be replaced by the secret value if the secret key matches the name of the storage endpoint.

If ``storage.endpointSecretName`` is empty, then the ``config.parameters`` will remained unchanged.

Storage Endpoint Examples
------------------------------

**SFTP Endpoint example:**

.. code-block:: shell

  endpoints:
    - name: SFTEndpoint
      location: DP
      storage_type: filesystem
      interface: posix
      root_directory: /
      config:
      name: SFTEndpoint
      type: sftp
      parameters: {"host":"myhost.com.au",
                   "user": "myuser",
                   "pass": "",
                   "key-pem": -----BEGIN RSA PRIVATE KEY-----\nMaMbaIXtE\n0gAMbMbaSsd\nMbaass\n-----END RSA PRIVATE KEY-----}

``key-pem`` can be generated by running the command: ``awk '{printf "%s\\n", $0}' < ~/.ssh/id_rsa``

Alternatively, one can specifiy the location of the key file by using ``key_file``.

Note that the public key must be put in the ``authorized_keys`` on the end point.


**S3 Endpoint example**

.. code-block:: shell

  endpoints:
    - name: dlm-archive
      location: AWS
      storage_type: objectstore
      interface: s3
      root_directory: /dlm-archive
      config:
      name: dlm-archive
      type: s3
      parameters: {"access_key_id": "access key",
                   "provider": "AWS",
                   "secret_access_key": "secret key",
                   "region": "ap-southeast-2",
                   "location_constraint": "ap-southeast-2"}


API Gateway
----------------

To install the OAuth API gateway:

  * Set ``gateway.enabled`` : ``true``
  * Set ``image`` to the registry path of the container image.
  * Set ``version`` to the container image version.
  * Set ``gateway.secret.name`` to the name of the k8 secret (see below).

Create a k8 secret with the following Entra configuration items obtained by SKAO IT:

  * ``PROVIDER`` : ``ENTRA``
  * ``TENANT_ID`` : ``<Tenant ID>``
  * ``CLIENT_ID`` : ``<Client ID>``
  * ``CLIENT_CRED`` : ``<Client credential>``


Benchmark
-----------

To run the benchmarking pod:

  * Set ``benchmark.enabled`` : ``true``
  * Set ``benchmark.name`` : ``register`` or ``migrate``
  * Set ``benchmark.config.host`` : hostname of the DLM gateway
  * Set ``benchmark.config.token`` : auth token
  * If ``benchmark.name`` : ``migrate``:
    * ``benchmark.config.sourceFile`` : name of the migration yaml config file (must be created in the directory ``charts/ska-dlm/benchmark``)
    * ``benchmark.config.mountPath`` : location in the pod the migration yaml config file will be copied

1) Setup port forwarding on the benchmark pod to port: ``8089``
2) In a browser, navigate to ``http://localhost:8089``
3) Click START

For details on the benchmark configuration, see `benchmark utilities <https://gitlab.com/ska-telescope/ska-data-lifecycle/-/tree/main/scripts#benchmark-utilities>`_ in the scripts readme.


Deploy DLM server
------------------

Finally, install the chart:

.. code-block:: bash

    helm upgrade --install ska-dlm [-n <namespace>] charts/ska-dlm

To uninstall the chart:

.. code-block:: bash

    helm uninstall [-n <namespace>] ska-dlm


.. Schema changes by release
.. -----------------------------

.. **Working version**

.. Note: The v1.1.2 directory holds the code required to migrate the database *from* 1.1.2 to the *next* release.

.. **Changes**:

.. * ``data_item.metadata`` column changed from ``json`` to ``jsonb``

