"""Phase heuristics related to placement and migration."""

from uuid import UUID

from sqlalchemy import select, update

from ska_dlm.common_types import PhaseType
from ska_dlm.dlm_db.models import DataItem, Storage
from ska_dlm.dlm_migration import _copy_data_item

from .common import PHASE_ORDER, BaseHeuristic, HeuristicResult
from .phase_combine import CombineUidPhasesHeuristic


class IncreaseOidPhaseHeuristic(BaseHeuristic):
    """Heuristic to increase OID phase resilience by creating additional UID instances."""

    def __init__(self, session):
        super().__init__(session)
        self.combine_heuristic = CombineUidPhasesHeuristic(session)
        self.identify_storage_heuristic = None

    async def execute(  # pylint: disable=arguments-differ,too-many-locals,too-many-return-statements
        self, oid: UUID, current_phase: PhaseType, target_phase: PhaseType
    ) -> HeuristicResult:
        """Execute the increase OID phase heuristic."""
        try:
            if PHASE_ORDER.get(target_phase, float("inf")) <= PHASE_ORDER.get(
                current_phase, float("inf")
            ):
                return HeuristicResult(
                    False,
                    f"Target phase {target_phase} does not provide higher resilience than "
                    f"current phase {current_phase}",
                )

            if self.identify_storage_heuristic is None:
                self.identify_storage_heuristic = IdentifyTargetStorageHeuristic(self.session)

            oid_stmt = select(DataItem).where(
                DataItem.OID == oid,
                DataItem.deleted.is_(False),
            )
            oid_result = await self.session.execute(oid_stmt)
            source_data_item = oid_result.scalar()

            if not source_data_item:
                return HeuristicResult(False, f"No data found for OID {oid}")

            storage_result = await self.identify_storage_heuristic.execute(oid, target_phase)
            if not storage_result.success:
                return HeuristicResult(
                    False,
                    f"Failed to identify target storage for OID {oid}: {storage_result.message}",
                )

            target_storage_id = storage_result.data["storage_id"]

            try:
                copy_result = await _copy_data_item(
                    self.session,
                    oid=str(oid),
                    destination_id=str(target_storage_id),
                    path=source_data_item.uri,
                )
            except Exception as copy_exc:  # pylint: disable=broad-exception-caught
                return HeuristicResult(
                    False,
                    f"Failed to copy data item for OID {oid}: {str(copy_exc)}",
                )

            if not copy_result or "uid" not in copy_result:
                return HeuristicResult(
                    False, f"Copy operation did not return new UID for OID {oid}"
                )

            new_uid = copy_result["uid"]
            migration_id = copy_result.get("migration_id", None)

            uid_stmt = select(Storage.storage_phase, DataItem.UID).where(
                DataItem.OID == oid,
                DataItem.deleted.is_(False),
                DataItem.storage_id == Storage.storage_id,
            )
            uid_result = await self.session.execute(uid_stmt)
            uid_rows = uid_result.fetchall()
            uid_phases = [row[0] for row in uid_rows]

            if uid_phases:
                combine_result = await self.combine_heuristic.execute(uid_phases)
                if not combine_result.success:
                    return HeuristicResult(
                        False,
                        f"Failed to combine UID phases for OID {oid}: {combine_result.message}",
                    )
                new_actual_phase = combine_result.data["actual_phase"]
            else:
                new_actual_phase = target_phase

            if new_actual_phase >= target_phase or PHASE_ORDER.get(
                new_actual_phase, float("inf")
            ) >= PHASE_ORDER.get(target_phase, float("inf")):
                update_stmt = (
                    update(DataItem).where(DataItem.OID == oid).values(OID_phase=new_actual_phase)
                )
                await self.session.execute(update_stmt)
                await self.session.commit()

                return self.success_result(
                    f"Created copy of OID {oid} in storage {target_storage_id}; "
                    f"OID phase updated to {new_actual_phase}",
                    {
                        "oid": oid,
                        "new_uid": new_uid,
                        "target_storage_id": target_storage_id,
                        "new_actual_phase": new_actual_phase,
                        "target_phase": target_phase,
                        "migration_id": migration_id,
                    },
                )

            return HeuristicResult(
                False,
                f"Copy operation did not reach target phase {target_phase}; "
                f"new actual phase is {new_actual_phase}",
                {
                    "oid": oid,
                    "new_uid": new_uid,
                    "target_storage_id": target_storage_id,
                    "new_actual_phase": new_actual_phase,
                    "target_phase": target_phase,
                    "migration_id": migration_id,
                },
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            await self.session.rollback()
            return HeuristicResult(
                False, f"Error executing Increase OID Phase heuristic: {str(exc)}"
            )


class IdentifyTargetStorageHeuristic(BaseHeuristic):
    """Heuristic to identify target storage for placing a new UID instance."""

    def __init__(self, session):
        super().__init__(session)
        self.combine_heuristic = CombineUidPhasesHeuristic(session)

    async def execute(  # pylint: disable=arguments-differ,too-many-locals
        self, oid: UUID, target_phase: PhaseType
    ) -> HeuristicResult:
        """Execute the identify target storage heuristic."""
        try:
            uid_stmt = select(Storage.storage_phase, DataItem.storage_id).where(
                DataItem.OID == oid,
                DataItem.deleted.is_(False),
                DataItem.storage_id == Storage.storage_id,
            )
            uid_result = await self.session.execute(uid_stmt)
            uid_rows = uid_result.fetchall()
            uid_phases = [row[0] for row in uid_rows]
            used_storage_ids = {row[1] for row in uid_rows}

            if uid_phases:
                combine_result = await self.combine_heuristic.execute(uid_phases)
                if not combine_result.success:
                    return combine_result
                actual_phase = combine_result.data["actual_phase"]
            else:
                actual_phase = PhaseType.PLASMA

            available_storage_stmt = select(Storage).where(
                Storage.storage_id.notin_(used_storage_ids) if used_storage_ids else True
            )
            available_storage_result = await self.session.execute(available_storage_stmt)
            available_storages = available_storage_result.scalars().all()

            if not available_storages:
                return HeuristicResult(
                    False,
                    f"No available storage found for OID {oid}",
                    {"status": "ERROR"},
                )

            target_order = PHASE_ORDER.get(target_phase, float("inf"))
            for storage in available_storages:
                storage_phase = storage.storage_phase
                storage_order = PHASE_ORDER.get(storage_phase, float("inf"))

                combined_order = PHASE_ORDER.get(actual_phase, 0) + storage_order
                if combined_order >= target_order:
                    return self.success_result(
                        f"Identified target storage {storage.storage_id} for OID {oid} "
                        f"to reach phase {target_phase}",
                        {
                            "storage_id": storage.storage_id,
                            "storage_phase": storage_phase,
                            "actual_phase": actual_phase,
                            "target_phase": target_phase,
                        },
                    )

            return HeuristicResult(
                False,
                f"No suitable storage found for OID {oid} to reach target phase {target_phase}",
                {"status": "ERROR"},
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            await self.session.rollback()
            return HeuristicResult(
                False, f"Error executing Identify Target Storage heuristic: {str(exc)}"
            )
