"""Helpers to infer screenshot type from extracted text."""
from __future__ import annotations

from ..db.enums import ScreenshotType

KEYWORD_MAP: list[tuple[str, ScreenshotType]] = [
    ("alliance member", ScreenshotType.ALLIANCE_MEMBERS),
    ("membership", ScreenshotType.ALLIANCE_MEMBERS),
    ("contribution", ScreenshotType.CONTRIBUTION),
    ("weekly contribution", ScreenshotType.CONTRIBUTION),
    ("bear", ScreenshotType.BEAR_EVENT),
    ("trap", ScreenshotType.BEAR_EVENT),
    ("lane", ScreenshotType.AC_LANES),
    ("championship", ScreenshotType.AC_LANES),
]


def infer_type_from_text(text: str, current: ScreenshotType) -> ScreenshotType:
    lowered = text.lower()
    for keyword, target in KEYWORD_MAP:
        if keyword in lowered:
            return target
    return current
