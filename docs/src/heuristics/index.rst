Heuristics Overview
===================
Individual heuristics are implemented as loadable classes based on an abstract class implementing a standard interface with the Heuristics Engine. That ensures that heuristics can be developed independently of the core DLM. Heuristics can also be nested, i.e. one heuristic can call others. This is required, since we always want to apply the same logic to certain operations (e.g. delete UID payload) and we also want to make sure that if that logic has to be changed it applies to all higher level heuristics using it. It also means that externally developed heuristics can make use of the core heuristics implemented by the DLM.

.. toctree::
   :maxdepth: 2
   :caption: Heuristics Details

   data_item_phase
   data_item_deletion
   data_item_expiry
