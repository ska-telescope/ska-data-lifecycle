Tango Monitoring
================

DLM provides a Tango device (``DLMMetrics``) for monitoring the health and operational status of the DLM subsystem.

The device exposes the following attributes:

* ``version``: DLM software version.
* ``image``: DLM container image.

* Individual service health states:

  - ``postgresHealthState``
  - ``postgrestHealthState``
  - ``rcloneHealthState``
  - ``heuristicsHealthState`` (_TODO_)
  - ``storageHealthState``
  - ``migrationHealthState``
  - ``ingestHealthState``
  - ``requestHealthState``
  - ``rabbitmqHealthState``

* ``storageEndPoints``: List of registered storage endpoints.
* ``migrationsInProgress``: Number of migrations currently in progress.
.. * ``storageUsedPct``: Percentage of storage capacity used at each endpoint. (TODO)
.. * ``dlmHealthState``: Overall health state of the DLM subsystem. (TODO)

For deployment and configuration instructions, see
:ref:`tango-helm-configuration`.
