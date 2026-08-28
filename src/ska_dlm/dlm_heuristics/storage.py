"""Storage-related heuristics."""

import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ska_dlm.common_types import PhaseType
from ska_dlm.dlm_db.models import DataItem, Storage
from ska_dlm.dlm_storage import dlm_storage_requests

from .common import BaseHeuristic, HeuristicResult
from .lifecycle import DeleteUidHeuristic
from .phase_combine import CombineUidPhasesHeuristic
from .phase_migration import IncreaseOidPhaseHeuristic

logger = logging.getLogger(__name__)


class UpdateStorageUsageHeuristic(BaseHeuristic):
    """Update registered storage endpoints with their current rclone usage."""

    async def execute(self) -> HeuristicResult:  # pylint: disable=arguments-differ,too-many-locals
        """Query rclone usage for every registered storage endpoint."""
        try:
            result = await self.session.execute(select(Storage))
            storages = result.scalars().all()
            if not storages:
                return self.success_result("No storage endpoints found", {"storages": []})

            storage_results = []
            for storage in storages:
                storage_id = storage.storage_id
                try:
                    config = dlm_storage_requests.get_storage_config(storage_id=str(storage_id))
                    if not config:
                        raise RuntimeError("No rclone configuration found")
                    volume = f"{config[0]['name']}:{config[0].get('root_path', '/')}"
                    about = dlm_storage_requests.rclone_about(volume)
                    total = int(about.get("total", -1))
                    used_stmt = select(func.coalesce(func.sum(DataItem.item_size), 0)).where(
                        DataItem.storage_id == storage_id,
                        DataItem.deleted.is_(False),
                    )
                    used_result = await self.session.execute(used_stmt)
                    used = int(used_result.scalar_one() or 0)
                    objects_stmt = select(
                        func.count(DataItem.UID)  # pylint: disable=not-callable
                    ).where(
                        DataItem.storage_id == storage_id,
                        DataItem.deleted.is_(False),
                    )
                    objects_result = await self.session.execute(objects_stmt)
                    objects = int(objects_result.scalar_one() or 0)
                    capacity_for_pct = (
                        storage.storage_capacity
                        if storage.storage_capacity not in [None, 0, -1]
                        else total
                    )
                    use_pct = (used / capacity_for_pct * 100) if capacity_for_pct > 0 else 0.0
                    update_values = {
                        "storage_use_pct": round(use_pct, 1) if use_pct < 100 else 99.9,
                        "storage_num_objects": objects,
                        "storage_available": True,
                        "storage_checked": True,
                        "storage_last_checked": func.now(),  # pylint: disable=not-callable
                    }
                    if storage.storage_capacity in [None, -1]:
                        update_values["storage_capacity"] = total
                    update_stmt = (
                        update(Storage)
                        .where(Storage.storage_id == storage_id)
                        .values(**update_values)
                    )
                    await self.session.execute(update_stmt)
                    storage_results.append(
                        {
                            "storage_id": storage_id,
                            "success": True,
                            "capacity": total,
                            "used": used,
                            "objects": objects,
                        }
                    )
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.warning("Unable to update storage usage for %s: %s", storage_id, exc)
                    unavailable_stmt = (
                        update(Storage)
                        .where(Storage.storage_id == storage_id)
                        .values(
                            storage_available=False,
                            storage_checked=True,
                            storage_last_checked=func.now(),  # pylint: disable=not-callable
                        )
                    )
                    await self.session.execute(unavailable_stmt)
                    storage_results.append(
                        {"storage_id": storage_id, "success": False, "message": str(exc)}
                    )

            # await self.session.commit()
            success = all(item["success"] for item in storage_results)
            message = "Updated storage usage" if success else "Some storage usage updates failed"
            return HeuristicResult(success, message, {"storages": storage_results})
        except Exception as exc:  # pylint: disable=broad-exception-caught
            await self.session.rollback()
            return HeuristicResult(False, f"Error updating storage usage: {str(exc)}")


class EnforceStorageUsageHeuristic(BaseHeuristic):
    """Enforce storage pressure limits with threshold hysteresis.

    This heuristic evaluates each storage endpoint and uses
    Storage.storage_use_pct as the authoritative utilization signal. Cleanup
    starts when usage reaches or exceeds threshold_pct, then continues until
    usage drops to threshold_pct minus 10 (floored at 0). Deletion candidates
    are selected by earliest effective expiration using UID and OID
    expiration timestamps. Storage metadata updates are delegated to
    DeleteUidHeuristic after each successful deletion.
    """

    def __init__(self, session: AsyncSession, threshold_pct: float = 80.0):
        super().__init__(session)
        self.threshold_pct = threshold_pct
        self.delete_heuristic = DeleteUidHeuristic(session)
        self.combine_heuristic = CombineUidPhasesHeuristic(session)
        self.increase_heuristic = IncreaseOidPhaseHeuristic(session)

    async def _current_phase_for_oid(self, oid) -> PhaseType:
        """Return combined current phase for non-deleted UIDs of an OID."""
        uid_stmt = select(Storage.storage_phase).where(
            DataItem.OID == oid,
            DataItem.deleted.is_(False),
            DataItem.storage_id == Storage.storage_id,
        )
        uid_result = await self.session.execute(uid_stmt)
        uid_phases = [row[0] for row in uid_result.fetchall()]
        if not uid_phases:
            return PhaseType.GAS

        combine_result = await self.combine_heuristic.execute(uid_phases)
        if combine_result.success:
            return combine_result.data["actual_phase"]
        return PhaseType.GAS

    async def _phase_after_uid_removed(self, oid, uid_to_remove) -> PhaseType:
        """Return resulting phase if a given UID were removed."""
        uid_stmt = select(Storage.storage_phase, DataItem.UID).where(
            DataItem.OID == oid,
            DataItem.deleted.is_(False),
            DataItem.storage_id == Storage.storage_id,
        )
        uid_result = await self.session.execute(uid_stmt)
        remaining_phases = [row[0] for row in uid_result.fetchall() if row[1] != uid_to_remove]
        if not remaining_phases:
            return PhaseType.GAS

        combine_result = await self.combine_heuristic.execute(remaining_phases)
        if combine_result.success:
            return combine_result.data["actual_phase"]
        return PhaseType.GAS

    async def _prepare_policy_compliant_delete(self, candidate) -> dict:
        """Try remediation when delete is blocked by target phase policy."""
        oid = getattr(candidate, "OID", None)
        target_phase = getattr(candidate, "target_phase", None)
        uid = getattr(candidate, "UID", None)
        if oid is None or target_phase is None or uid is None:
            return {"action": "none", "message": "Candidate missing OID/target_phase/UID"}

        # Compare with the phase after deletion, else increase_heuristic will not do anything.
        future_phase = await self._phase_after_uid_removed(oid, uid)
        increase_result = await self.increase_heuristic.execute(oid, future_phase, target_phase)
        if increase_result.success:
            return {
                "action": "replicated_for_target_phase",
                "message": increase_result.message,
            }

        lowered_target_phase = await self._phase_after_uid_removed(oid, uid)
        update_target_stmt = (
            update(DataItem)
            .where(DataItem.OID == oid, DataItem.deleted.is_(False))
            .values(target_phase=lowered_target_phase)
        )
        await self.session.execute(update_target_stmt)
        return {
            "action": "lowered_target_phase",
            "target_phase": lowered_target_phase,
            "message": "Lowered target phase to permit deletion",
        }

    @staticmethod
    def _expiration_rank(item: DataItem) -> tuple[float, float, float]:
        """Return sort keys for deletion priority.

        Priority is based on the earliest known expiry (minimum of UID/OID
        expiration), then by OID expiration, then UID expiration.

        Parameters
        ----------
        item
            Data item candidate whose expiration timestamps are used for
            ranking.
        """
        uid_exp = item.UID_expiration.timestamp() if item.UID_expiration else float("inf")
        oid_exp = item.OID_expiration.timestamp() if item.OID_expiration else float("inf")
        return (min(uid_exp, oid_exp), oid_exp, uid_exp)

    async def execute(self) -> HeuristicResult:  # pylint: disable=arguments-differ,too-many-locals
        """Apply storage pressure cleanup for all registered storages.

        The method validates required storage fields, decides whether
        enforcement should run, and if needed deletes soonest-expiring items
        until the hysteresis target is reached or no candidates remain. The
        result summarizes per-storage outcomes and reports success only when
        each storage is either below threshold or has reached the lower
        hysteresis target.
        """
        try:
            stmt = select(Storage)
            result = await self.session.execute(stmt)
            storages = result.scalars().all()
            if not storages:
                return self.success_result("No storage endpoints found", {"storages": []})

            storage_results = []
            for storage in storages:
                storage_id = storage.storage_id
                capacity = storage.storage_capacity

                if capacity in [None, 0, -1]:
                    storage_results.append(
                        {
                            "storage_id": storage_id,
                            "success": False,
                            "message": "No valid storage capacity",
                        }
                    )
                    continue

                used_stmt = select(func.coalesce(func.sum(DataItem.item_size), 0)).where(
                    DataItem.storage_id == storage_id,
                    DataItem.deleted.is_(False),
                )
                used_result = await self.session.execute(used_stmt)
                used = int(used_result.scalar_one() or 0)
                storage_use_pct = storage.storage_use_pct
                if storage_use_pct in [None, -1]:
                    storage_results.append(
                        {
                            "storage_id": storage_id,
                            "success": False,
                            "message": f"No valid storage_use_pct: {storage_use_pct}",
                        }
                    )
                    continue
                use_pct = float(storage_use_pct)
                target_use_pct = max(0.0, self.threshold_pct - 10.0)
                should_enforce = use_pct >= self.threshold_pct

                candidates_stmt = select(DataItem).where(
                    DataItem.storage_id == storage_id,
                    DataItem.deleted.is_(False),
                )
                candidates_result = await self.session.execute(candidates_stmt)
                candidates = sorted(
                    candidates_result.scalars().all(),
                    key=self._expiration_rank,
                )

                deletion_results = []
                object_count = len(candidates)
                while should_enforce and use_pct > target_use_pct and candidates:
                    candidate = candidates.pop(0)
                    delete_result = await self.delete_heuristic.execute(candidate.UID)

                    remediation = None
                    if (
                        not delete_result.success
                        and "Deletion would violate resilience policy" in delete_result.message
                    ):
                        remediation = await self._prepare_policy_compliant_delete(candidate)
                        delete_result = await self.delete_heuristic.execute(candidate.UID)

                    deletion_results.append(
                        {
                            "uid": candidate.UID,
                            "success": delete_result.success,
                            "message": delete_result.message,
                            "remediation": remediation,
                        }
                    )

                    if delete_result.success:
                        used = max(0, used - int(candidate.item_size or 0))
                        object_count = max(0, object_count - 1)
                        pct_delta = int(candidate.item_size or 0) / capacity * 100
                        use_pct = max(0.0, use_pct - pct_delta)

                storage_results.append(
                    {
                        "storage_id": storage_id,
                        "success": (use_pct <= target_use_pct if should_enforce else True),
                        "used": used,
                        "capacity": capacity,
                        "target_use_pct": round(target_use_pct, 1),
                        "use_pct": round(use_pct, 1),
                        "deletion_results": deletion_results,
                    }
                )

            # await self.session.commit()
            success = all(item["success"] for item in storage_results)
            message = (
                "Enforced storage usage threshold"
                if success
                else "Errors encountered: Some storages remain above usage threshold"
            )
            return HeuristicResult(success, message, {"storages": storage_results})
        except Exception as exc:  # pylint: disable=broad-exception-caught
            await self.session.rollback()
            return HeuristicResult(False, f"Error enforcing storage usage threshold: {str(exc)}")
