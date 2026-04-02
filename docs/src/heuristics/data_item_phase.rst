Data Item Phases
================
The data_item phase encodes the resilience of a data_item against loss. The actual physical resilience is an operational definition, depending on which storage technology SKA operations regards as to having no (PLASMA), low (GAS), mid (LIQUID) or high (SOLID) resilience. Data items (referred to by their UID) inherit their resilience, or ``uid_phase`` from the storage volume they are residing on. An OID refers to a set of UIDs or instances of the same ``data_item`` on different storage volumes. We also have an ``oid_phase`` which is calculated using the heuristics described below from the ``uid_phases``, but is always equal or higher than each of those. 


OID Phase Enforce Heuristic
+++++++++++++++++++++++++++
The OID Phase Enforce heuristic is checking the consistency between the OID phase and combination of all UID phases and the required target phase and acts according to the result. It calls upon the Combine Phase, Increase and Decrease Phase heuristics. The main logic here is that the actual phase of an OID should be equal  to the logically combined phase of all UIDs and the actual phase also has to satisfy the required target phase.

.. image:: ../_static/img/oid_phase_enforce.svg


Combine UID Phase Heuristic
+++++++++++++++++++++++++++
Not yet implemented

.. image:: ../_static/img/combine_uid_phases.svg

Increase OID Phase Heuristic
++++++++++++++++++++++++++++

.. image:: ../_static/img/increase_oid_phase.svg

Decrease OID Phase Heuristic
++++++++++++++++++++++++++++

.. image:: ../_static/img/decrease_oid_phase.svg
