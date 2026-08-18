"""Core phase-management heuristics."""

from uuid import UUID

from sqlalchemy import select, update

from ska_dlm.common_types import PhaseType
from ska_dlm.dlm_db.models import DataItem, Storage

from .common import PHASE_ORDER, BaseHeuristic, HeuristicResult
from .phase_combine import CombineUidPhasesHeuristic
from .phase_migration import IncreaseOidPhaseHeuristic


class ChangeOidPhaseHeuristic(BaseHeuristic):
    """Heuristic to change OID phase by deleting or creating UID replicas."""

    def __init__(self, session):
        super().__init__(session)
        self.combine_heuristic = CombineUidPhasesHeuristic(session)
        from .lifecycle import DeleteUidHeuristic

        self.delete_heuristic = DeleteUidHeuristic(session)
        self.increase_heuristic = None

    async def execute(self, oid: UUID, target_phase: PhaseType = None) -> HeuristicResult:
        """Execute the change OID phase heuristic."""
        try:
            if self.increase_heuristic is None:
                self.increase_heuristic = IncreaseOidPhaseHeuristic(self.session)

            stmt = select(DataItem).where(DataItem.OID == oid)
            result = await self.session.execute(stmt)
            data_item = result.scalar()

            if not data_item:
                return HeuristicResult(False, f"No data found for OID {oid}")

            if target_phase is None:
                target_phase = data_item.target_phase

            current_phase = data_item.OID_phase

            uid_stmt = select(Storage.storage_phase, DataItem.UID).where(
                DataItem.OID == oid,
                DataItem.deleted.is_(False),
                DataItem.storage_id == Storage.storage_id,
            )
            uid_result = await self.session.execute(uid_stmt)
            uid_rows = uid_result.fetchall()
            uid_phases = [row[0] for row in uid_rows]
            all_uids = [row[1] for row in uid_rows]

            if not uid_phases:
                return HeuristicResult(False, f"No UIDs found for OID {oid}")

            combine_result = await self.combine_heuristic.execute(uid_phases)
            if not combine_result.success:
                return combine_result

            actual_phase = combine_result.data["actual_phase"]

            target_order = PHASE_ORDER.get(target_phase, float("inf"))
            actual_order = PHASE_ORDER.get(actual_phase, float("inf"))

            if target_order < actual_order:
                deletion_results = []
                current_result_phase = actual_phase

                for uid in all_uids:
                    if current_result_phase == target_phase:
                        break

                    delete_result = await self.delete_heuristic.execute(uid)
                    deletion_results.append(
                        {
                            "uid": uid,
                            "success": delete_result.success,
                            "message": delete_result.message,
                        }
                    )

                    if delete_result.success and "result_phase" in delete_result.data:
                        current_result_phase = delete_result.data["result_phase"]
                    elif not delete_result.success:
                        break

                if current_result_phase != target_phase:
                    return HeuristicResult(
                        False,
                        f"Failed to reach target phase {target_phase}; reached {current_result_phase}",
                        {"deletion_results": deletion_results},
                    )

                update_stmt = (
                    update(DataItem).where(DataItem.OID == oid).values(OID_phase=target_phase)
                )
                await self.session.execute(update_stmt)
                await self.session.commit()

                return self.success_result(
                    f"Deleted UID instances to reach OID {oid} target phase {target_phase}",
                    {
                        "oid": oid,
                        "target_phase": target_phase,
                        "result_phase": current_result_phase,
                        "deletion_results": deletion_results,
                    },
                )

            if target_order > actual_order:
                return await self.increase_heuristic.execute(oid, actual_phase, target_phase)

            if current_phase != actual_phase:
                update_stmt = (
                    update(DataItem).where(DataItem.OID == oid).values(OID_phase=actual_phase)
                )
                await self.session.execute(update_stmt)
                await self.session.commit()

            return self.success_result(
                f"OID {oid} already at target phase {target_phase}",
                {
                    "oid": oid,
                    "target_phase": target_phase,
                    "current_phase": actual_phase,
                },
            )

        except Exception as exc:
            await self.session.rollback()
            return HeuristicResult(
                False, f"Error executing Change OID Phase heuristic: {str(exc)}"
            )


class OidPhaseEnforceHeuristic(BaseHeuristic):
    """Heuristic to enforce OID phase consistency with UID phases and target phase."""

    def __init__(self, session):
        super().__init__(session)
        self.combine_heuristic = CombineUidPhasesHeuristic(session)
        self.increase_heuristic = IncreaseOidPhaseHeuristic(session)
        self.decrease_heuristic = DecreaseOidPhaseHeuristic(session)

    async def execute(self, oid: UUID) -> HeuristicResult:
        """Execute the OID Phase Enforce heuristic."""
        try:
            stmt = select(DataItem).where(DataItem.OID == oid)
            result = await self.session.execute(stmt)
            data_item = result.scalar()

            if not data_item:
                return HeuristicResult(False, f"No data found for OID {oid}")

            oid_phase = data_item.OID_phase
            target_phase = data_item.target_phase

            uid_stmt = select(Storage.storage_phase).where(
                DataItem.OID == oid, DataItem.storage_id == Storage.storage_id
            )
            uid_result = await self.session.execute(uid_stmt)
            uid_phases = [row[0] for row in uid_result.fetchall()]

            combine_result = await self.combine_heuristic.execute(uid_phases)
            if not combine_result.success:
                return combine_result

            actual_phase = combine_result.data["actual_phase"]

            if target_phase == actual_phase and oid_phase != actual_phase:
                update_stmt = (
                    update(DataItem).where(DataItem.OID == oid).values(OID_phase=actual_phase)
                )
                await self.session.execute(update_stmt)
                await self.session.commit()
                return self.success_result(f"Updated OID {oid} phase to {actual_phase}")

            if PHASE_ORDER.get(target_phase, float("inf")) < PHASE_ORDER.get(
                actual_phase, float("inf")
            ):
                return await self.decrease_heuristic.execute(oid, oid_phase, target_phase)

            if PHASE_ORDER.get(target_phase, float("inf")) > PHASE_ORDER.get(
                actual_phase, float("inf")
            ):
                return await self.increase_heuristic.execute(oid, oid_phase, target_phase)

            return self.success_result(f"OID {oid} phases are consistent")

        except Exception as exc:
            await self.session.rollback()
            return HeuristicResult(
                False, f"Error executing OID Phase Enforce heuristic: {str(exc)}"
            )


class DecreaseOidPhaseHeuristic(BaseHeuristic):
    """Heuristic to decrease OID phase resilience by deleting UID instances."""

    def __init__(self, session):
        super().__init__(session)
        from .lifecycle import DeleteUidHeuristic

        self.delete_heuristic = DeleteUidHeuristic(session)
        self.combine_heuristic = CombineUidPhasesHeuristic(session)

    async def execute(
        self, oid: UUID, current_phase: PhaseType, target_phase: PhaseType
    ) -> HeuristicResult:
        """Execute the decrease OID phase heuristic."""
        try:
            if PHASE_ORDER.get(target_phase, float("inf")) >= PHASE_ORDER.get(
                current_phase, float("inf")
            ):
                return HeuristicResult(
                    False,
                    f"Target phase {target_phase} does not provide lower resilience than "
                    f"current phase {current_phase}",
                )

            uid_stmt = select(DataItem.UID).where(
                DataItem.OID == oid,
                DataItem.deleted.is_(False),
            )
            uid_result = await self.session.execute(uid_stmt)
            all_uids = [row[0] for row in uid_result.fetchall()]

            if not all_uids:
                return HeuristicResult(False, f"No UIDs found for OID {oid}")

            deletion_results = []
            for uid in all_uids:
                delete_result = await self.delete_heuristic.execute(uid)
                deletion_results.append(
                    {
                        "uid": uid,
                        "success": delete_result.success,
                        "message": delete_result.message,
                    }
                )

                if delete_result.success:
                    uid_stmt = select(DataItem.OID_phase).where(DataItem.UID == uid)
                    phase_result = await self.session.execute(uid_stmt)
                    phase_row = phase_result.scalar()

                    if phase_row == target_phase:
                        break
                elif not delete_result.success:
                    break

            current_stmt = select(DataItem.OID_phase).where(DataItem.OID == oid)
            current_result = await self.session.execute(current_stmt)
            current_phase_result = current_result.scalar()

            if current_phase_result == target_phase:
                return self.success_result(
                    f"Successfully decreased OID {oid} phase to {target_phase}",
                    {
                        "oid": oid,
                        "target_phase": target_phase,
                        "deletion_results": deletion_results,
                    },
                )
            return HeuristicResult(
                False,
                f"Failed to reach target phase {target_phase}; current phase is {current_phase_result}",
                {"deletion_results": deletion_results},
            )

        except Exception as exc:
            await self.session.rollback()
            return HeuristicResult(
                False, f"Error executing Decrease OID Phase heuristic: {str(exc)}"
            )
