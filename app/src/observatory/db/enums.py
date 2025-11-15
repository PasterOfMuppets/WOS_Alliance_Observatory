"""Shared enumeration types for persistence layer."""
from __future__ import annotations

from enum import Enum


class ScreenshotStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ScreenshotType(str, Enum):
    UNKNOWN = "unknown"
    ALLIANCE_MEMBERS = "alliance_members"
    CONTRIBUTION = "contribution"
    AC_LANES = "ac_lanes"
    BEAR_EVENT = "bear_event"


class PlayerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"


class EventStatType(str, Enum):
    POWER = "power"
    FURNACE = "furnace"
    CONTRIBUTION = "contribution"
    BEAR = "bear"
    CUSTOM = "custom"
