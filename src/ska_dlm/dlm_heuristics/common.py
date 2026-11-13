"""Shared heuristic primitives and phase ordering helpers."""

from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ska_dlm.common_types import PhaseType

PHASE_ORDER = {v: p for p, v in enumerate(PhaseType)}
PHASE_ORDER[PhaseType.SOLID] = 4
n_PHASE_ORDER = {v: k for k, v in PHASE_ORDER.items()}


class HeuristicResult:  # pylint: disable=too-few-public-methods
    """Result of a heuristic execution."""

    def __init__(self, success: bool, message: str = "", data: Optional[dict] = None):
        self.success = success
        self.message = message
        self.data = data or {}


class BaseHeuristic(ABC):
    """Abstract base class for all heuristics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def execute(self, **kwargs) -> HeuristicResult:
        """Execute the heuristic logic.

        Args
        ----
        kwargs : dict
            Heuristic-specific parameters

        Returns
        -------
        HeuristicResult
            The result of the heuristic execution
        """

    @classmethod
    def success_result(cls, message: str = "", data: Optional[dict] = None) -> HeuristicResult:
        """Create a successful heuristic result."""
        return HeuristicResult(True, message, data)
