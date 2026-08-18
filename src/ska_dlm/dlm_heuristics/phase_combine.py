"""Phase-combination heuristic."""

from typing import List

from ska_dlm.common_types import PhaseType

from .common import PHASE_ORDER, BaseHeuristic, HeuristicResult, n_PHASE_ORDER


class CombineUidPhasesHeuristic(BaseHeuristic):
    """Heuristic to combine UID phases into a single actual phase."""

    async def execute(self, uid_phases: List[PhaseType]) -> HeuristicResult:
        """Combine UID phases to determine the actual phase for an OID."""
        if not uid_phases:
            return HeuristicResult(False, "No UID phases provided")

        n_GAS = uid_phases.count(PhaseType.GAS)
        n_LIQUID = uid_phases.count(PhaseType.LIQUID)
        n_SOLID = uid_phases.count(PhaseType.SOLID)
        n_combined_phase = (
            n_GAS * PHASE_ORDER[PhaseType.GAS]
            + n_LIQUID * PHASE_ORDER[PhaseType.LIQUID]
            + n_SOLID * PHASE_ORDER[PhaseType.SOLID]
        )
        if n_combined_phase == 3:
            n_combined_phase = 2
        combined_phase = n_PHASE_ORDER[min(n_combined_phase, 4)]
        return self.success_result(
            f"Combined phase: {combined_phase}", {"actual_phase": combined_phase}
        )
