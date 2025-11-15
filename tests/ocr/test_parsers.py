from __future__ import annotations

from io import BytesIO

from PIL import Image

from observatory.db.enums import ScreenshotType
from observatory.ocr.parsers import AllianceMembersParser, _extract_ranked_entries
from observatory.ocr.classifier import ClassificationResult
from observatory.ocr.dataset import ScreenshotSample
from observatory.ocr.image_loader import load_image


def _make_image_bytes(size=(100, 50), color=(200, 200, 200), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def _classification(sample: ScreenshotSample, detected_type: ScreenshotType) -> ClassificationResult:
    img = load_image(sample.path)
    return ClassificationResult(sample=sample, detected_type=detected_type, confidence=0.5, loader_output=img)


def test_roster_parser_extracts_players(tmp_path):
    path = tmp_path / "sample.png"
    path.write_bytes(_make_image_bytes())
    sample = ScreenshotSample(path=path, type=ScreenshotType.ALLIANCE_MEMBERS)
    classification = _classification(sample, ScreenshotType.ALLIANCE_MEMBERS)
    parser = AllianceMembersParser()
    result = parser.parse(sample, classification, "Alpha 120000\nBeta 50000")
    assert result.payload["players"][0]["name"] == "Alpha"


def test_ranked_entries_detection():
    text = "La SHARKCAN 41,160\nASemx SAAAM6 41,040\nBaz abc"
    entries = _extract_ranked_entries(text)
    assert len(entries) == 2
    assert entries[0]["value"] == 41160
