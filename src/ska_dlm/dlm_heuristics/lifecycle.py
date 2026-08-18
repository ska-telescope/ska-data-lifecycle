"""Lifecycle and deletion-oriented heuristics."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update

from ska_dlm.common_types import ItemState, PhaseType
from ska_dlm.dlm_db.models import DataItem, Storage
from ska_dlm.dlm_storage import dlm_storage_requests

from .common import PHASE_ORDER, BaseHeuristic, HeuristicResult

logger = logging.getLogger(__name__)


class DeleteUidHeuristic(BaseHeuristic):
    """Heuristic to safely delete a UID payload while preserving OID resilience."""

    def __init__(self, session):
        super().__init__(session)
        from .phase_combine import CombineUidPhasesHeuristic

        self.combine_heuristic = CombineUidPhasesHeuristic(session)

    async def _mark_uid_as_deleted(self, uid: UUID) -> None:
        """Mark a UID as deleted in the database."""
        update_uid_stmt = (
            update(DataItem)
            .where(DataItem.UID == uid)
            .values(
                item_state=ItemState.DELETED,
                deleted=True,
                UID_deletion=func.now(),  # pylint: disable=not-callable
            )
        )
        await self.session.execute(update_uid_stmt)

    async def _update_storage_after_delete(
        self, storage_id: Optional[UUID], deleted_item_size: Optional[int]
    ) -> None:
        """Update storage use percentage and object count after a successful delete."""
        if not isinstance(storage_id, (UUID, str)):
            return

        storage_stmt = select(Storage.storage_use_pct, Storage.storage_capacity).where(
            Storage.storage_id == storage_id
        )
        storage_result = await self.session.execute(storage_stmt)
        storage_row = storage_result.first()
        if not storage_row:
            return
        if not isinstance(storage_row, (tuple, list)) or len(storage_row) != 2:
            return

        storage_use_pct, storage_capacity = storage_row
        if (
            isinstance(storage_use_pct, (int, float))
            and storage_use_pct >= 0
            and isinstance(storage_capacity, (int, float))
            and storage_capacity > 0
            and isinstance(deleted_item_size, int)
            and deleted_item_size > 0
        ):
            pct_delta = deleted_item_size / storage_capacity * 100
            new_use_pct = max(0.0, float(storage_use_pct) - pct_delta)
        else:
            new_use_pct = (
                float(storage_use_pct) if isinstance(storage_use_pct, (int, float)) else 0.0
            )

        objects_stmt = select(func.count(DataItem.UID)).where(
            DataItem.storage_id == storage_id,
            DataItem.deleted.is_(False),
        )
        objects_result = await self.session.execute(objects_stmt)
        object_count = int(objects_result.scalar_one() or 0)

        update_storage_stmt = (
            update(Storage)
            .where(Storage.storage_id == storage_id)
            .values(
                storage_use_pct=round(new_use_pct, 1),
                storage_num_objects=object_count,
                storage_checked=True,
                storage_last_checked=func.now(),
            )
        )
        await self.session.execute(update_storage_stmt)

    async def _check_parent_deleted(self, uid: UUID) -> bool:
        """Return True when the parent DataItem is already marked as deleted."""
        stmt = select(DataItem.parents).where(
            DataItem.UID == uid,
            DataItem.parents.is_not(None),
        )
        result = await self.session.execute(stmt)
        parent_uid = result.scalar_one_or_none()
        if parent_uid is None:
            return False

        stmt = select(DataItem.item_state).where(DataItem.UID == parent_uid)
        result = await self.session.execute(stmt)
        parent_state = result.scalar_one_or_none()
        return parent_state == ItemState.DELETED

    def _get_storage_accessibility(
        self, uid: UUID, data_item
    ) -> tuple[bool, bool, Optional[UUID]]:
        """Return normalized item/storage metadata and accessibility state for a UID."""
        storage_id = getattr(data_item, "storage_id", None)
        storage_id_is_known = isinstance(storage_id, (UUID, str))

        storage_accessible = True
        item_accessible = True
        if storage_id_is_known:
            try:
                storage_accessible = bool(
                    dlm_storage_requests.check_storage_access(storage_id=str(storage_id))
                )
                item_accessible = (
                    str(storage_id)
                    == dlm_storage_requests.check_item_on_storage(
                        uid=str(uid), storage_id=str(storage_id)
                    )[0]["storage_id"]
                )
            except Exception:
                storage_accessible = False
                item_accessible = False

        return storage_accessible, item_accessible, storage_id

    async def _collect_remaining_replica_state(
        self, oid: UUID, uid_to_remove: UUID
    ) -> tuple[list[PhaseType], list[dict], bool]:
        """Collect accessible phases and inaccessible replica metadata for remaining UIDs."""
        uid_stmt = select(DataItem, Storage.storage_phase).where(
            DataItem.OID == oid,
            DataItem.deleted.is_(False),
            DataItem.storage_id == Storage.storage_id,
        )
        uid_result = await self.session.execute(uid_stmt)

        accessible_remaining_phases: list[PhaseType] = []
        inaccessible_replicas: list[dict] = []
        any_remaining = False

        for row in uid_result.fetchall():
            if hasattr(row[0], "UID"):
                remaining_item = row[0]
                remaining_phase = row[1]
            else:
                remaining_phase = row[0]
                remaining_uid = row[1]
                remaining_item = type(
                    "RemainingItem",
                    (),
                    {"UID": remaining_uid, "storage_id": None},
                )()

            if remaining_item.UID == uid_to_remove:
                continue

            any_remaining = True
            (
                remaining_storage_accessible,
                remaining_item_accessible,
                remaining_storage_id,
            ) = self._get_storage_accessibility(remaining_item.UID, remaining_item)

            if remaining_storage_accessible and remaining_item_accessible:
                accessible_remaining_phases.append(remaining_phase)
            else:
                inaccessible_replicas.append(
                    {
                        "uid": remaining_item.UID,
                        "storage_id": remaining_storage_id,
                        "storage_accessible": remaining_storage_accessible,
                        "item_accessible": remaining_item_accessible,
                    }
                )

        return accessible_remaining_phases, inaccessible_replicas, any_remaining

    async def _compute_result_phase(
        self, accessible_remaining_phases: list[PhaseType], any_remaining: bool
    ) -> tuple[Optional[PhaseType], Optional[HeuristicResult]]:
        """Compute resulting OID phase after candidate UID deletion."""
        if accessible_remaining_phases:
            combine_result = await self.combine_heuristic.execute(accessible_remaining_phases)
            if not combine_result.success:
                return None, combine_result
            return combine_result.data["actual_phase"], None

        if any_remaining:
            return PhaseType.PLASMA, None
        return PhaseType.GAS, None

    @staticmethod
    def _build_delete_kwargs(data_item) -> dict:
        """Build optional delete payload kwargs from data item metadata."""
        delete_kwargs = {}
        item_type = getattr(data_item, "item_type", None)
        item_name = getattr(data_item, "item_name", None)
        if isinstance(item_type, str) and item_type:
            delete_kwargs["item_type"] = item_type
        if isinstance(item_name, str) and item_name:
            delete_kwargs["item_name"] = item_name
        return delete_kwargs

    async def _delete_payload(self, uid: UUID, data_item) -> Optional[HeuristicResult]:
        """Delete payload from storage manager and return a failure result if it fails."""
        delete_kwargs = self._build_delete_kwargs(data_item)
        item_name = getattr(data_item, "item_name", None)

        try:
            delete_result = dlm_storage_requests.delete_data_item_payload(
                str(uid), **delete_kwargs
            )
        except TypeError as exc:
            if "item_name" not in str(exc) and "unexpected keyword argument" not in str(exc):
                raise
            delete_kwargs.pop("item_name", None)
            delete_result = dlm_storage_requests.delete_data_item_payload(
                str(uid), **delete_kwargs
            )

        if not delete_result:
            item_name = item_name or str(uid)
            return HeuristicResult(False, f"Failed to delete payload for {item_name} {uid}")
        return None

    async def _mark_container_children_deleted(self, uid: UUID, data_item) -> None:
        """Mark child UIDs as deleted when the deleted item is a container."""
        if data_item.item_type is None or data_item.item_type.lower() != "container":
            return

        stmt = select(DataItem.UID).where(DataItem.parents == uid)
        result = await self.session.execute(stmt)
        child_uids = result.scalars().all()
        for child_uid in child_uids:
            if await self._check_parent_deleted(child_uid):
                await self._mark_uid_as_deleted(child_uid)
                logger.debug("Marked child_uid as deleted: %s", child_uid)

    async def execute(self, uid: UUID) -> HeuristicResult:
        """Execute UID deletion heuristic according to deletion sequence diagram."""
        try:
            stmt = select(DataItem).where(DataItem.UID == uid)
            result = await self.session.execute(stmt)
            data_item = result.scalar()

            if not data_item:
                return HeuristicResult(False, f"No data found for UID {uid}")

            if not data_item.OID:
                return HeuristicResult(False, f"UID {uid} has no associated OID")

            oid = data_item.OID
            target_phase = data_item.target_phase
            (
                storage_accessible,
                item_accessible,
                storage_id,
            ) = self._get_storage_accessibility(uid, data_item)

            if not item_accessible and isinstance(storage_id, (UUID, str)) and storage_accessible:
                await self._mark_uid_as_deleted(uid)
                await self._update_storage_after_delete(
                    storage_id,
                    getattr(data_item, "item_size", None),
                )
                await self.session.commit()
                return self.success_result(
                    f"UID {uid} marked as deleted.",
                    {
                        "uid": uid,
                        "oid": oid,
                        "storage_id": storage_id,
                        "storage_accessible": storage_accessible,
                        "item_accessible": item_accessible,
                    },
                )

            (
                accessible_remaining_phases,
                inaccessible_replicas,
                any_remaining,
            ) = await self._collect_remaining_replica_state(oid, uid)
            result_phase, combine_error = await self._compute_result_phase(
                accessible_remaining_phases,
                any_remaining,
            )
            if combine_error:
                return combine_error

            if PHASE_ORDER[result_phase] < PHASE_ORDER[target_phase]:
                return HeuristicResult(
                    False,
                    "Deletion would violate resilience policy",
                    {
                        "oid": oid,
                        "uid": uid,
                        "result_phase": result_phase,
                        "target_phase": target_phase,
                        "accessible_replica_count": len(accessible_remaining_phases),
                        "inaccessible_replicas": inaccessible_replicas,
                    },
                )

            delete_error = await self._delete_payload(uid, data_item)
            if delete_error:
                return delete_error

            await self._mark_uid_as_deleted(uid)
            await self._update_storage_after_delete(
                storage_id,
                getattr(data_item, "item_size", None),
            )
            await self._mark_container_children_deleted(uid, data_item)

            update_oid_stmt = (
                update(DataItem).where(DataItem.OID == oid).values(OID_phase=result_phase)
            )
            await self.session.execute(update_oid_stmt)

            await self.session.commit()

            return self.success_result(
                f"Deleted UID {uid} payload and updated OID {oid} phase to {result_phase}",
                {"uid": uid, "oid": oid, "result_phase": result_phase},
            )

        except Exception as exc:
            await self.session.rollback()
            return HeuristicResult(False, f"Error executing UID deletion heuristic: {str(exc)}")


class UidExpiryHeuristic(BaseHeuristic):
    """Heuristic to discover expired UIDs and delegate deletion."""

    def __init__(self, session):
        super().__init__(session)
        self.delete_heuristic = DeleteUidHeuristic(session)

    async def execute(self) -> HeuristicResult:
        """Execute the UID expiry heuristic."""
        try:
            stmt = select(DataItem.UID).where(
                DataItem.UID_expiration < func.now(),  # pylint: disable=not-callable
                DataItem.deleted.is_(False),
            )
            result = await self.session.execute(stmt)
            expired_rows = result.fetchall()
            expired_uids = [row[0] for row in expired_rows]

            if not expired_uids:
                return self.success_result("No expired UIDs found", {"expired_uids": []})

            deletion_results = []
            for uid in expired_uids:
                delete_result = await self.delete_heuristic.execute(uid)
                deletion_results.append(
                    {
                        "uid": uid,
                        "success": delete_result.success,
                        "message": delete_result.message,
                    }
                )
                if not delete_result.success:
                    logger.info("Deletion of UID %s failed: %s", uid, delete_result.message)

            success = all(item["success"] for item in deletion_results)
            message = "Deleted expired UIDs" if success else "Some expired UID deletions failed"

            return HeuristicResult(
                success,
                message,
                {"expired_uids": expired_uids, "deletion_results": deletion_results},
            )

        except Exception as exc:
            await self.session.rollback()
            return HeuristicResult(False, f"Error executing UID expiry heuristic: {str(exc)}")


class OidExpiryHeuristic(BaseHeuristic):
    """Heuristic to discover expired OIDs and delete their UIDs."""

    def __init__(self, session):
        super().__init__(session)
        self.delete_heuristic = DeleteUidHeuristic(session)

    async def execute(self) -> HeuristicResult:
        """Execute the OID expiry heuristic."""
        try:
            stmt = (
                select(DataItem.OID)
                .distinct()
                .where(
                    DataItem.OID_expiration < func.now(),  # pylint: disable=not-callable
                    DataItem.deleted.is_(False),
                    DataItem.OID.is_not(None),
                )
            )
            result = await self.session.execute(stmt)
            expired_rows = result.fetchall()
            expired_oids = [row[0] for row in expired_rows]

            if not expired_oids:
                return self.success_result("No expired OIDs found", {"expired_oids": []})

            deletion_results = []
            for oid in expired_oids:
                update_target_phase_stmt = (
                    update(DataItem)
                    .where(DataItem.OID == oid, DataItem.deleted.is_(False))
                    .values(target_phase=PhaseType.PLASMA)
                )
                await self.session.execute(update_target_phase_stmt)

                uid_stmt = select(DataItem.UID).where(
                    DataItem.OID == oid,
                    DataItem.deleted.is_(False),
                )
                uid_result = await self.session.execute(uid_stmt)
                uid_rows = uid_result.fetchall()
                for uid_row in uid_rows:
                    uid = uid_row[0]
                    delete_result = await self.delete_heuristic.execute(uid)
                    deletion_results.append(
                        {
                            "oid": oid,
                            "uid": uid,
                            "success": delete_result.success,
                            "message": delete_result.message,
                        }
                    )

            success = all(item["success"] for item in deletion_results)
            message = "Deleted expired OIDs" if success else "Some expired OID deletions failed"

            return HeuristicResult(
                success,
                message,
                {"expired_oids": expired_oids, "deletion_results": deletion_results},
            )

        except Exception as exc:
            await self.session.rollback()
            return HeuristicResult(False, f"Error executing OID expiry heuristic: {str(exc)}")
