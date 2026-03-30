Data Item Expiration
====================
For each registered data_item the DLM the system keeps two expiration datetime stamps. One (OID expiration) indicating the expiration of the data_item globally, means *all* instances of this data_item on *all* storage volumes. The other expiration datetime stamp is for one individual instance of that data_item. If a data_item is expired the DLM *can* delete it, but it will not delete it immediately. If the global expiration time has passed the system will eventually delete all instances of that data_item everywhere.

UID Expiration Heuristics
-------------------------
The UID expiration datetime field enables automatic cleanup of an individual instance of a data_item on a specific storage volume. If the UID expiration datetimestamp has passed, the DLM *is allowed* to delete the associated data on the storage volume holding the data_item with that UID. The heuristic involved in making the decision about actual deletion or not is depicted in the sequence diagram below. Note that the ``Execution`` **is calling** the ``uid_delete`` heuristic and will thus only delete the data if the OID phase after deletion is at least preserved.

.. image:: ../_static/img/uid_expiry_diagram.svg
   :alt: UID Expiration Diagram

OID Expiration Heuristics
-------------------------
The OID expiration datetime field enables automatic cleanup of all instances of a data_item on any storage volume controlled by the DLM. If the OID expiration timestamp has passed the DLM *is allowed* to delete all the associated data referred to by that OID. In effect the heuristic depicted in the sequence diagram below loops over all UIDs related to an OID and deletes them one-by-one. If one or more of the UIDs can't be deleted all the others will still be deleted and also not re-instantiated in order to free up as much space as possible. The state of the OID deletion is still FAILED in this case. The UID deletion does **not** call the ``uid_delete`` heuristic, since that would also check whether the UID has actually expired. This is equivalent to saying that the OID expiration datetime overrides the UID expiration datetime. 

.. image:: ../_static/img/oid_expiry_diagram.svg
   :alt: OID Expiration Diagram
