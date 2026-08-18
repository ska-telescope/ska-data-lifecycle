"""Backward-compatible export surface for DLM heuristics.

The concrete heuristic implementations are split across focused modules:
- common.py
- storage.py
- lifecycle.py
- phase.py
"""

from ska_dlm.dlm_storage import dlm_storage_requests

from .common import PHASE_ORDER, BaseHeuristic, HeuristicResult, n_PHASE_ORDER
from .lifecycle import DeleteUidHeuristic, OidExpiryHeuristic, UidExpiryHeuristic
from .phase import (
    ChangeOidPhaseHeuristic,
    CombineUidPhasesHeuristic,
    DecreaseOidPhaseHeuristic,
    IdentifyTargetStorageHeuristic,
    IncreaseOidPhaseHeuristic,
    OidPhaseEnforceHeuristic,
)
from .storage import EnforceStorageUsageHeuristic, UpdateStorageUsageHeuristic

__all__ = [
    "dlm_storage_requests",
    "PHASE_ORDER",
    "n_PHASE_ORDER",
    "HeuristicResult",
    "BaseHeuristic",
    "UpdateStorageUsageHeuristic",
    "EnforceStorageUsageHeuristic",
    "CombineUidPhasesHeuristic",
    "ChangeOidPhaseHeuristic",
    "DeleteUidHeuristic",
    "UidExpiryHeuristic",
    "OidExpiryHeuristic",
    "OidPhaseEnforceHeuristic",
    "IncreaseOidPhaseHeuristic",
    "DecreaseOidPhaseHeuristic",
    "IdentifyTargetStorageHeuristic",
]
