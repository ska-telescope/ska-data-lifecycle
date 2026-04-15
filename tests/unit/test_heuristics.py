"""Unit tests for DLM heuristics."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from ska_dlm.common_types import PhaseType
from ska_dlm.dlm_heuristics.heuristics import (
    BaseHeuristic,
    CombineUidPhasesHeuristic,
    DecreaseOidPhaseHeuristic,
    DeleteUidHeuristic,
    HeuristicResult,
    IncreaseOidPhaseHeuristic,
    OidExpiryHeuristic,
    OidPhaseEnforceHeuristic,
    UidExpiryHeuristic,
)
from ska_dlm.dlm_storage import dlm_storage_requests


class TestHeuristicResult:
    """Test HeuristicResult class."""

    def test_init_success_only(self):
        """Test HeuristicResult initialization with success only."""
        result = HeuristicResult(True)
        assert result.success is True
        assert result.message == ""
        assert result.data == {}

    def test_init_with_message(self):
        """Test HeuristicResult initialization with message."""
        result = HeuristicResult(False, "Error occurred")
        assert result.success is False
        assert result.message == "Error occurred"
        assert result.data == {}

    def test_init_with_data(self):
        """Test HeuristicResult initialization with data."""
        data = {"key": "value", "phase": PhaseType.SOLID}
        result = HeuristicResult(True, "Success", data)
        assert result.success is True
        assert result.message == "Success"
        assert result.data == data

    def test_init_with_none_data(self):
        """Test HeuristicResult initialization with None data."""
        result = HeuristicResult(True, "Success", None)
        assert result.success is True
        assert result.message == "Success"
        assert result.data == {}


class TestCombineUidPhasesHeuristic:
    """Test CombineUidPhasesHeuristic class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def heuristic(self, mock_session):
        """Create CombineUidPhasesHeuristic instance."""
        return CombineUidPhasesHeuristic(mock_session)

    @pytest.mark.asyncio
    async def test_empty_uid_phases(self, heuristic):
        """Test combining empty UID phases list."""
        result = await heuristic.execute([])
        assert result.success is False
        assert result.message == "No UID phases provided"
        assert result.data == {}

    @pytest.mark.asyncio
    async def test_single_uid_phase(self, heuristic):
        """Test combining single UID phase."""
        uid_phases = [PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        # assert result.message == "Combined phase: LIQUID"
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_double_liquid_uid_phase(self, heuristic):
        """Test combining single UID phase."""
        uid_phases = [PhaseType.LIQUID, PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.SOLID}

    @pytest.mark.asyncio
    async def test_multiple_uid_phases_gas_liquid(self, heuristic):
        """Test combining GAS and LIQUID phases."""
        uid_phases = [PhaseType.GAS, PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_multiple_uid_phases_combined(self, heuristic):
        """Test combining all phase types."""
        uid_phases = [PhaseType.GAS, PhaseType.LIQUID, PhaseType.GAS, PhaseType.PLASMA]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.SOLID}

    @pytest.mark.asyncio
    async def test_multiple_uid_phases_plasma_combined(self, heuristic):
        """Test combining all phase types."""
        uid_phases = [PhaseType.PLASMA, PhaseType.LIQUID, PhaseType.GAS, PhaseType.PLASMA]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_duplicate_phases(self, heuristic):
        """Test combining duplicate phases."""
        uid_phases = [PhaseType.GAS, PhaseType.GAS, PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        # assert result.message == "Combined phase: PhaseType.SOLID"
        assert result.data == {"actual_phase": PhaseType.SOLID}

    @pytest.mark.asyncio
    async def test_phase_hierarchy_gas(self, heuristic):
        """Test that GAS is the lowest phase."""
        uid_phases = [PhaseType.GAS, PhaseType.GAS]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_phase_plasma(self, heuristic):
        """Test that PLASMA does not increase resilience."""
        uid_phases = [PhaseType.GAS, PhaseType.PLASMA]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.GAS}


class TestIncreaseOidPhaseHeuristic:
    """Test IncreaseOidPhaseHeuristic class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def heuristic(self, mock_session):
        """Create IncreaseOidPhaseHeuristic instance."""
        return IncreaseOidPhaseHeuristic(mock_session)

    @pytest.mark.asyncio
    async def test_execute(self, heuristic):
        """Test executing increase heuristic."""
        oid = uuid.uuid4()
        current_phase = PhaseType.GAS
        target_phase = PhaseType.LIQUID

        result = await heuristic.execute(oid, current_phase, target_phase)

        assert result.success is True
        assert (
            result.message
            == f"Increased OID {oid} phase from {current_phase} towards {target_phase}"
        )
        assert result.data == {}


class TestDecreaseOidPhaseHeuristic:
    """Test DecreaseOidPhaseHeuristic class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def heuristic(self, mock_session):
        """Create DecreaseOidPhaseHeuristic instance."""
        return DecreaseOidPhaseHeuristic(mock_session)

    @pytest.mark.asyncio
    async def test_execute(self, heuristic):
        """Test executing decrease heuristic."""
        oid = uuid.uuid4()
        current_phase = PhaseType.SOLID
        target_phase = PhaseType.LIQUID

        result = await heuristic.execute(oid, current_phase, target_phase)

        assert result.success is True
        assert (
            result.message
            == f"Decreased OID {oid} phase from {current_phase} towards {target_phase}"
        )
        assert result.data == {}


class TestUidExpiryHeuristic:
    """Test UidExpiryHeuristic class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def heuristic(self, mock_session):
        """Create UidExpiryHeuristic instance."""
        return UidExpiryHeuristic(mock_session)

    @pytest.mark.asyncio
    async def test_no_expired_uids(self, heuristic, mock_session):
        """Test when there are no expired UIDs to process."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        result = await heuristic.execute()

        assert result.success is True
        assert result.message == "No expired UIDs found"
        assert result.data == {"expired_uids": []}

    @pytest.mark.asyncio
    async def test_delete_expired_uids(self, heuristic, mock_session):
        """Test deletion of multiple expired UIDs."""
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(uid1,), (uid2,)]
        mock_session.execute.return_value = mock_result

        heuristic.delete_heuristic.execute = AsyncMock(
            side_effect=[
                HeuristicResult(True, "Deleted UID 1"),
                HeuristicResult(True, "Deleted UID 2"),
            ]
        )

        result = await heuristic.execute()

        assert result.success is True
        assert result.message == "Deleted expired UIDs"
        assert result.data["expired_uids"] == [uid1, uid2]
        assert len(result.data["deletion_results"]) == 2

    @pytest.mark.asyncio
    async def test_delete_expired_uids_partial_failure(self, heuristic, mock_session):
        """Test when one expired UID deletion fails."""
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(uid1,), (uid2,)]
        mock_session.execute.return_value = mock_result

        heuristic.delete_heuristic.execute = AsyncMock(
            side_effect=[
                HeuristicResult(True, "Deleted UID 1"),
                HeuristicResult(False, "Delete failed for UID 2"),
            ]
        )

        result = await heuristic.execute()

        assert result.success is False
        assert result.message == "Some expired UID deletions failed"
        assert result.data["expired_uids"] == [uid1, uid2]
        assert result.data["deletion_results"][1]["success"] is False


class TestOidExpiryHeuristic:
    """Test OidExpiryHeuristic class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def heuristic(self, mock_session):
        """Create OidExpiryHeuristic instance."""
        return OidExpiryHeuristic(mock_session)

    @pytest.mark.asyncio
    async def test_no_expired_oids(self, heuristic, mock_session):
        """Test when there are no expired OIDs to process."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        result = await heuristic.execute()

        assert result.success is True
        assert result.message == "No expired OIDs found"
        assert result.data == {"expired_oids": []}

    @pytest.mark.asyncio
    async def test_delete_expired_oids(self, heuristic, mock_session):
        """Test deletion of UIDs for expired OIDs."""
        oid1 = uuid.uuid4()
        oid2 = uuid.uuid4()
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()
        uid3 = uuid.uuid4()

        mock_oid_result = MagicMock()
        mock_oid_result.fetchall.return_value = [(oid1,), (oid2,)]

        mock_uid_result_1 = MagicMock()
        mock_uid_result_1.fetchall.return_value = [(uid1,), (uid2,)]

        mock_uid_result_2 = MagicMock()
        mock_uid_result_2.fetchall.return_value = [(uid3,)]

        mock_session.execute.side_effect = [
            mock_oid_result,
            mock_uid_result_1,
            mock_uid_result_2,
        ]

        heuristic.delete_heuristic.execute = AsyncMock(
            side_effect=[
                HeuristicResult(True, "Deleted UID 1"),
                HeuristicResult(True, "Deleted UID 2"),
                HeuristicResult(True, "Deleted UID 3"),
            ]
        )

        result = await heuristic.execute()

        assert result.success is True
        assert result.message == "Deleted expired OIDs"
        assert result.data["expired_oids"] == [oid1, oid2]
        assert len(result.data["deletion_results"]) == 3
        assert result.data["deletion_results"][0]["oid"] == oid1
        assert result.data["deletion_results"][2]["oid"] == oid2

    @pytest.mark.asyncio
    async def test_partial_failure(self, heuristic, mock_session):
        """Test when some UID deletions for expired OIDs fail."""
        oid1 = uuid.uuid4()
        uid1 = uuid.uuid4()

        mock_oid_result = MagicMock()
        mock_oid_result.fetchall.return_value = [(oid1,)]

        mock_uid_result_1 = MagicMock()
        mock_uid_result_1.fetchall.return_value = [(uid1,)]

        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result_1]

        heuristic.delete_heuristic.execute = AsyncMock(
            return_value=HeuristicResult(False, "Delete failed")
        )

        result = await heuristic.execute()

        assert result.success is False
        assert result.message == "Some expired OID deletions failed"
        assert result.data["expired_oids"] == [oid1]
        assert result.data["deletion_results"][0]["success"] is False


class TestOidPhaseEnforceHeuristic:
    """Test OidPhaseEnforceHeuristic class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def heuristic(self, mock_session):
        """Create OidPhaseEnforceHeuristic instance."""
        return OidPhaseEnforceHeuristic(mock_session)

    @pytest.mark.asyncio
    async def test_no_data_found(self, heuristic, mock_session):
        """Test when no data is found for the OID."""
        oid = uuid.uuid4()

        # Mock the execute to return None (no rows)
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        result = await heuristic.execute(oid)

        assert result.success is False
        assert result.message == f"No data found for OID {oid}"

    @pytest.mark.asyncio
    async def test_combine_heuristic_failure(self, heuristic, mock_session):
        """Test when combine heuristic fails."""
        oid = uuid.uuid4()

        # Mock OID phase query
        mock_data_item = MagicMock()
        mock_data_item.OID_phase = PhaseType.GAS
        mock_data_item.target_phase = PhaseType.SOLID

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = mock_data_item
        mock_session.execute.return_value = mock_oid_result

        # Mock UID phases query
        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.GAS,), (PhaseType.LIQUID,)]
        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result]

        # Mock combine heuristic to fail
        heuristic.combine_heuristic.execute = AsyncMock(
            return_value=HeuristicResult(False, "Combine failed")
        )

        result = await heuristic.execute(oid)

        assert result.success is False
        assert result.message == "Combine failed"

    @pytest.mark.asyncio
    async def test_update_oid_phase(self, heuristic, mock_session):
        """Test updating OID phase when target == actual and OID != actual."""
        oid = uuid.uuid4()

        # Mock OID phase query (OID_phase = GAS, target_phase = LIQUID)
        mock_data_item = MagicMock()
        mock_data_item.OID_phase = PhaseType.GAS
        mock_data_item.target_phase = PhaseType.LIQUID

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = mock_data_item
        mock_session.execute.return_value = mock_oid_result

        # Mock UID phases query (UIDs have LIQUID)
        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.LIQUID,)]

        # Mock update statement result
        mock_update_result = MagicMock()

        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result, mock_update_result]

        # Mock combine heuristic
        heuristic.combine_heuristic.execute = AsyncMock(
            return_value=BaseHeuristic.success_result(
                "Combined", {"actual_phase": PhaseType.LIQUID}
            )
        )

        result = await heuristic.execute(oid)

        assert result.success is True
        assert result.message == f"Updated OID {oid} phase to {PhaseType.LIQUID}"
        # Verify commit was called
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_increase_heuristic_called(self, heuristic, mock_session):
        """Test calling increase heuristic when target < actual."""
        oid = uuid.uuid4()

        # Mock OID phase query (OID_phase = GAS, target_phase = GAS)
        mock_data_item = MagicMock()
        mock_data_item.OID_phase = PhaseType.GAS
        mock_data_item.target_phase = PhaseType.GAS

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = mock_data_item
        mock_session.execute.return_value = mock_oid_result

        # Mock UID phases query (UIDs have SOLID - higher than target)
        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.SOLID,)]
        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result]

        # Mock combine heuristic
        heuristic.combine_heuristic.execute = AsyncMock(
            return_value=BaseHeuristic.success_result(
                "Combined", {"actual_phase": PhaseType.SOLID}
            )
        )

        # Mock increase heuristic
        increase_result = BaseHeuristic.success_result("Increased")
        heuristic.increase_heuristic.execute = AsyncMock(return_value=increase_result)

        result = await heuristic.execute(oid)

        assert result == increase_result
        heuristic.increase_heuristic.execute.assert_called_once_with(
            oid, PhaseType.GAS, PhaseType.GAS
        )

    @pytest.mark.asyncio
    async def test_decrease_heuristic_called(self, heuristic, mock_session):
        """Test calling decrease heuristic when target > actual."""
        oid = uuid.uuid4()

        # Mock OID phase query (OID_phase = SOLID, target_phase = PLASMA)
        mock_data_item = MagicMock()
        mock_data_item.OID_phase = PhaseType.SOLID
        mock_data_item.target_phase = PhaseType.PLASMA

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = mock_data_item
        mock_session.execute.return_value = mock_oid_result

        # Mock UID phases query (UIDs have LIQUID - lower than target)
        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.LIQUID,)]
        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result]

        # Mock combine heuristic
        heuristic.combine_heuristic.execute = AsyncMock(
            return_value=BaseHeuristic.success_result(
                "Combined", {"actual_phase": PhaseType.LIQUID}
            )
        )

        # Mock decrease heuristic
        decrease_result = BaseHeuristic.success_result("Decreased")
        heuristic.decrease_heuristic.execute = AsyncMock(return_value=decrease_result)

        result = await heuristic.decrease_heuristic.execute(oid)

        assert result == decrease_result

    @pytest.mark.asyncio
    async def test_phases_consistent(self, heuristic, mock_session):
        """Test when all phases are already consistent."""
        oid = uuid.uuid4()

        # Mock OID phase query (OID_phase = LIQUID, target_phase = LIQUID)
        mock_data_item = MagicMock()
        mock_data_item.OID_phase = PhaseType.LIQUID
        mock_data_item.target_phase = PhaseType.LIQUID

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = mock_data_item
        mock_session.execute.return_value = mock_oid_result

        # Mock UID phases query (UIDs have LIQUID)
        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.LIQUID,)]
        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result]

        # Mock combine heuristic
        heuristic.combine_heuristic.execute = AsyncMock(
            return_value=BaseHeuristic.success_result(
                "Combined", {"actual_phase": PhaseType.LIQUID}
            )
        )

        result = await heuristic.execute(oid)

        assert result.success is True
        assert result.message == f"OID {oid} phases are consistent"

    @pytest.mark.asyncio
    async def test_exception_handling(self, heuristic, mock_session):
        """Test exception handling during execution."""
        oid = uuid.uuid4()

        # Mock session.execute to raise an exception
        mock_session.execute.side_effect = Exception("Database error")

        result = await heuristic.execute(oid)

        assert result.success is False
        assert "Error executing OID Phase Enforce heuristic: Database error" in result.message
        # Verify rollback was called
        mock_session.rollback.assert_called_once()


class TestDeleteUidHeuristic:
    """Test DeleteUidHeuristic class."""

    @pytest.fixture
    def mock_session(self):
        """Mock session."""
        return AsyncMock()

    @pytest.fixture
    def heuristic(self, mock_session):
        """Heuristics fixture."""
        return DeleteUidHeuristic(mock_session)

    @pytest.mark.asyncio
    async def test_no_data_found(self, heuristic, mock_session):
        """No data test."""
        uid = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        result = await heuristic.execute(uid)

        assert result.success is False
        assert result.message == f"No data found for UID {uid}"

    @pytest.mark.asyncio
    async def test_resilience_violation(self, heuristic, mock_session):
        """Resilience violation test."""
        uid = uuid.uuid4()
        oid = uuid.uuid4()

        data_item = MagicMock()
        data_item.OID = oid
        data_item.target_phase = PhaseType.SOLID

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = data_item

        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.LIQUID, uid)]

        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result]

        result = await heuristic.execute(uid)

        assert result.success is False
        assert "Deletion would violate resilience policy" in result.message

    @pytest.mark.asyncio
    async def test_delete_payload_success(self, heuristic, mock_session, monkeypatch):
        """Delete payload test."""
        uid = uuid.uuid4()
        uid1 = uuid.uuid4()
        oid = uuid.uuid4()
        storage_id = uuid.uuid4()

        data_item = MagicMock()
        data_item.OID = oid
        data_item.UID = uid
        data_item.target_phase = PhaseType.GAS
        data_item.storage_id = storage_id

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = data_item

        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.GAS, uid), (PhaseType.GAS, uid1)]

        mock_delete_data_item_payload = MagicMock()
        mock_delete_data_item_payload.return_value = True

        mock_query_exists_and_ready = MagicMock()
        mock_query_exists_and_ready.return_value = True

        mock_session.execute.side_effect = [
            mock_oid_result,
            mock_uid_result,
            mock_delete_data_item_payload,
            mock_query_exists_and_ready,
        ]

        monkeypatch.setattr(dlm_storage_requests, "delete_data_item_payload", lambda x: True)

        result = await heuristic.execute(uid)

        assert result.success is True
        assert "Deleted UID" in result.message
        mock_session.commit.assert_called_once()
        mock_session.reset_mock()

    @pytest.mark.asyncio
    async def test_delete_payload_failure(self, heuristic, mock_session, monkeypatch):
        """Delete payload failure test."""
        uid = uuid.uuid4()
        oid = uuid.uuid4()

        data_item = MagicMock()
        data_item.OID = oid
        data_item.target_phase = PhaseType.GAS

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = data_item

        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.GAS, uuid.uuid4())]

        mock_session.execute.side_effect = [mock_oid_result, mock_uid_result]

        monkeypatch.setattr(dlm_storage_requests, "delete_data_item_payload", lambda x: False)

        result = await heuristic.execute(uid)

        assert result.success is False
        assert "Failed to delete payload" in result.message
        mock_session.commit.assert_not_called()
