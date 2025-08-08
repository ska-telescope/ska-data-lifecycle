"""JSON utilities for SKA DLM."""

import json
import uuid
from typing import Any


class UUIDEncoder(json.JSONEncoder):
    """JSON encoder that can handle UUID objects."""

    def default(self, obj: Any) -> Any:
        """Convert UUID objects to strings.

        Parameters
        ----------
        obj : Any
            The object to convert.

        Returns
        -------
        Any
            The converted object.
        """
        if isinstance(obj, uuid.UUID):
            # Convert UUID objects to strings
            return str(obj)
        # Let the base class handle other types
        return super().default(obj)