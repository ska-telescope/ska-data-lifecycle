Data Item Deletion
===================
Once a data_item is registered with the DLM the database records will be maintained, even if the actual data payload is deleted from the storage volumes. In order to support this the DLM maintains a status flag in the DB and one of the possible values is ``DELETED``, which means that the data payload does not exist anymore. There is also the value ``EXPIRED``, which is reduant with the datetime stamps, but enables a much quicker query for the heuristics task. 

UID Deletion Heuristics
-----------------------
Data items can not be deleted without proper checks of the current and resulting resilience phase. If the resulting ``oid_phase`` would be lower than the ``target_phase``, the system should not simply delete the UID payload. In the sequence diagram below this situation will lead to an error being raised. In future implementations of this heuristics we may want to create another UID on another volume and then delete the requested one. This alternate path relies on having enough flexibility in the available storage volumes, but as long as that is not the case there is very little that could be done.

.. image:: ../_static/img/deletion_diagram.svg
