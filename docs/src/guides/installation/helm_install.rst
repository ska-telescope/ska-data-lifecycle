Helm Install
=============

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
* ``postgresql.enabled``: If true, a local PostgreSQL instance will be deployed. Otherwise, an external PostgreSQL service is assumed, and auth details must be given through a secret (via ``ska-db-migrations.dbCredentialsSecretName``).
* ``postgresql.primary.persistence.enabled``: If enabled, PostgreSQL will persist data between executions; otherwise it will start from scratch each time.
* ``ska-db-migrations.runMigrations``: True by default. When enabled, a Liquibase job is run to apply database migrations during deployment.

Authentication
---------------

Database authentication details for PostgREST are provided via a Kubernetes ``Secret``.

- ``postgrest.db_auth_secret.create``: Whether to create the Secret.

  * If ``true`` (default for ``postgresql.enabled=true``), the Secret is created automatically
    using the credentials defined under ``postgresql.auth``:

    - ``postgresql.auth.username``
    - ``postgresql.auth.password``
    - ``postgresql.auth.database``

  * If ``false``, an existing Secret must be provided via
    ``ska-db-migrations.dbCredentialsSecretName``.

- In all cases, the Secret must contain the following keys:
  ``PGHOST``, ``PGUSER``, ``PGPASSWORD`` and ``PGDATABASE``.

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

Web IDE access to Postgres can be enabled by deploying pgweb in the cluster by setting ``pgweb.enabled`` : ``true``. Once deployed, the pgweb interface can be accessed by port-forwarding the pgweb service or pod. For example, when using k9s, select the ``pgweb`` pod and press ``Shift+F`` to forward the default port (``8081``). Then open a browser and navigate to ``http://localhost:8081/``.
Log in using the appropriate database credentials. If you deployed a local Postgres instance, these correspond to the values defined under ``postgresql.auth`` in your ``values.yaml`` file.


.. _database-migrations:

Database Migrations
---------------------

Database migrations are executed by Kubernetes Job resources as part of the Helm deployment process.
These Jobs run Liquibase to apply schema changes defined in the migration scripts.

Migrations are managed by the ``ska-db-migrations`` subchart and are enabled by default.
When enabled, a short-lived Job is created during deployment to run the Liquibase changelog
against the configured PostgreSQL database.

The behaviour of the migration process can be controlled using Helm values, such as:

- ``ska-db-migrations.runMigrations``: Enables or disables running migrations
- ``ska-db-migrations.liquibase.contextFilter``: Controls which changesets are applied

If migrations are disabled (not recommended), the database must be pre-initialised and already conform to the latest schema version before deployment.

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
  - ``storage_phase``: storage phase (``GAS``, ``LIQUID``, ``SOLID``)
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
      storage_phase: GAS
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
      storage_phase: SOLID
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
  * Set ``gateway.image`` to the registry path of the container image.
  * Set ``gateway.version`` to the container image version.
  * Set ``gateway.secret.name`` to the name of the k8 secret (see below).

Create a k8 secret with the following Entra configuration items obtained by SKAO IT:

  * ``PROVIDER`` : ``ENTRA``
  * ``TENANT_ID`` : ``<Tenant ID>``
  * ``CLIENT_ID`` : ``<Client ID>``
  * ``CLIENT_CRED`` : ``<Client credential>``

Both ``gateway.enabled`` must be set ``true`` and ``gateway.secret.name`` has to be supplied for the gateway pod to be deployed.

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
2) In a browser, navigate to ``http://localhost:8089``.  Now you should see a Locust GUI.
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


