Data Item Expiration
====================
For each registered data_item the DLM the system keeps two expiration datetime stamps. One (OID expiration) indicating the expiration of the data_item globally, means *all* instances of this data_item on *all* storage volumes. The other expiration datetime stamp is for one individual instance of that data_item. If a data_item is expired the DLM *can* delete it, but it will not delete it immediately. If the global expiration time has passed the system will eventually delete all instances of that data_item everywhere.

UID Expiration Heuristics
-------------------------
**<insert sequence diagram>**

OID Expiration Heuristics
-------------------------
**<insert sequence diagram>**