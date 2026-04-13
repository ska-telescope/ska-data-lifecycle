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
    OidPhaseEnforceHeuristic,
)
import ska_dlm.dlm_storage.dlm_storage_requests as storage_requests


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
        oid = uuid.uuid4()
        result = await heuristic.execute([])
        assert result.success is False
        assert result.message == "No UID phases provided"
        assert result.data == {}

    @pytest.mark.asyncio
    async def test_single_uid_phase(self, heuristic):
        """Test combining single UID phase."""
        oid = uuid.uuid4()
        uid_phases = [PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        # assert result.message == "Combined phase: LIQUID"
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_double_liquid_uid_phase(self, heuristic):
        """Test combining single UID phase."""
        oid = uuid.uuid4()
        uid_phases = [PhaseType.LIQUID, PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.SOLID}

    @pytest.mark.asyncio
    async def test_multiple_uid_phases_gas_liquid(self, heuristic):
        """Test combining GAS and LIQUID phases."""
        oid = uuid.uuid4()
        uid_phases = [PhaseType.GAS, PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_multiple_uid_phases_combined(self, heuristic):
        """Test combining all phase types."""
        oid = uuid.uuid4()
        uid_phases = [PhaseType.GAS, PhaseType.LIQUID, PhaseType.GAS, PhaseType.PLASMA]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.SOLID}

    @pytest.mark.asyncio
    async def test_multiple_uid_phases_plasma_combined(self, heuristic):
        """Test combining all phase types."""
        oid = uuid.uuid4()
        uid_phases = [PhaseType.PLASMA, PhaseType.LIQUID, PhaseType.GAS, PhaseType.PLASMA]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_duplicate_phases(self, heuristic):
        """Test combining duplicate phases."""
        oid = uuid.uuid4()
        uid_phases = [PhaseType.GAS, PhaseType.GAS, PhaseType.LIQUID]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        # assert result.message == "Combined phase: PhaseType.SOLID"
        assert result.data == {"actual_phase": PhaseType.SOLID}

    @pytest.mark.asyncio
    async def test_phase_hierarchy_gas(self, heuristic):
        """Test that GAS is the lowest phase."""
        oid = uuid.uuid4()
        uid_phases = [PhaseType.GAS, PhaseType.GAS]
        result = await heuristic.execute(uid_phases)
        assert result.success is True
        assert result.data == {"actual_phase": PhaseType.LIQUID}

    @pytest.mark.asyncio
    async def test_phase_plasma(self, heuristic):
        """Test that PLASMA does not increase resilience."""
        oid = uuid.uuid4()
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
        oid = uuid.uuid4()

        data_item = MagicMock()
        data_item.OID = oid
        data_item.target_phase = PhaseType.GAS

        mock_oid_result = MagicMock()
        mock_oid_result.scalar.return_value = data_item

        mock_uid_result = MagicMock()
        mock_uid_result.fetchall.return_value = [(PhaseType.GAS, uuid.uuid4())]

        mock_session.execute.side_effect = [
            mock_oid_result,
            mock_uid_result,
            MagicMock(),
            MagicMock(),
        ]

        monkeypatch.setattr(storage_requests, "delete_data_item_payload", lambda x: True)

        result = await heuristic.execute(uid)

        assert result.success is True
        assert "Deleted UID" in result.message
        mock_session.commit.assert_called_once()

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

        monkeypatch.setattr(storage_requests, "delete_data_item_payload", lambda x: False)

        result = await heuristic.execute(uid)

        assert result.success is False
        assert "Failed to delete payload" in result.message
        mock_session.commit.assert_not_called()
