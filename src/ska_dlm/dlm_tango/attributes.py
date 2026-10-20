"""Device attribute values."""

import enum


@enum.unique
class HealthState(enum.IntEnum):
    """Health state attribute values."""

    OK = 0
    DEGRADED = 1
    FAILED = 2
    UNKNOWN = 3
