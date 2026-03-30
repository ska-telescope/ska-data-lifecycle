Data Item Deletion
===================
Once a data_item is registered with the DLM the database records will be maintained, even if the actual data payload is deleted from the storage volumes. In order to support this the DLM maintains a status flag in the DB and one of the possible values is ``DELETED``, which means that the data payload does not exist anymore. There is also the value ``EXPIRED``, which is reduant with the datetime stamps, but enables a much quicker query for the heuristics task.

UID Deletion Heuristics
-----------------------
.. image:: ../_static/img/resilient_data_removal.svg
