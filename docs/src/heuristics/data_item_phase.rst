Data Item Phases
================
The data_item phase encodes the resilience of a data_item against loss. The actual physical resilience is an operational definition, depending on which storage technology SKA operations regards as to having no (PLASMA), low (GAS), mid (LIQUID) or high (SOLID) resilience. Data items (referred to by their UID) inherit their resilience, or ``uid_phase`` from the storage volume they are residing on. An OID refers to a set of UIDs or instances of the same ``data_item`` on different storage volumes. We also have an ``oid_phase`` which is calculated using the heuristics described below from the ``uid_phases``, but is always equal or higher than each of those. 


OID Phase Enforce Heuristic
+++++++++++++++++++++++++++
The OID Phase Enforce heuristic is checking the consistency between the OID phase and combination of all UID phases and the required target phase and acts according to the result. It calls upon the Combine Phase, Increase and Decrease Phase heuristics. The main logic here is that the actual phase of an OID should be equal  to the logically combined phase of all UIDs and the actual phase also has to satisfy the required target phase.

.. image:: ../_static/img/oid_phase_enforce.svg


Combine UID Phase Heuristic
+++++++++++++++++++++++++++
This heuristic is used by other heuristics to determine the combined phase (``actual_phase``) of a data_item referred to by an ``OID``. If the data_item is in a consistent state the ``actual_phase`` should be the same as the ``oid_phase``, which is also held in the DLM DB. 

.. image:: ../_static/img/combine_uid_phases.svg

Change OID Phase Heuristic
++++++++++++++++++++++++++++
This heuristic, if called directly, will attempt to change the OID phase to reach the requested target phase. This can be achieved by adding or removing an additional instance of the ``data_item`` or by moving it to a storage volume providing a higher/lower phase (resilience). This heuristic makes use of the ``combine_uid_phases`` heuristic above.

.. image:: ../_static/img/oid_phase_change.svg
