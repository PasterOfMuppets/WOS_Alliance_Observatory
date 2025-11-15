from __future__ import annotations

from observatory.db.enums import ScreenshotType
from observatory.ocr.text_inference import infer_type_from_text


def test_infer_type_from_text_detects_keywords() -> None:
    text = "Weekly Contribution Rankings\\nPlayer 1 123"
    result = infer_type_from_text(text, ScreenshotType.UNKNOWN)
    assert result == ScreenshotType.CONTRIBUTION


def test_infer_type_from_text_keeps_existing() -> None:
    text = "random text"
    result = infer_type_from_text(text, ScreenshotType.BEAR_EVENT)
    assert result == ScreenshotType.BEAR_EVENT
