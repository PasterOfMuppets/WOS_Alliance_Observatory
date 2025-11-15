from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from observatory.db.enums import ScreenshotType
from observatory.ocr.classifier import HeuristicClassifier
from observatory.ocr.dataset import ScreenshotSample


def _make_image_bytes(size=(100, 50), color=(255, 255, 255), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def test_heuristic_classifier_with_keywords(tmp_path: Path) -> None:
    image_path = tmp_path / "bear_event_sample.png"
    image_path.write_bytes(_make_image_bytes())

    sample = ScreenshotSample(path=image_path, type=ScreenshotType.UNKNOWN)
    classifier = HeuristicClassifier()

    result = classifier.classify(sample)
    assert result.detected_type == ScreenshotType.BEAR_EVENT
    assert 0.0 <= result.confidence <= 1.0
    assert result.loader_output.width == 100


def test_heuristic_classifier_uses_note(tmp_path: Path) -> None:
    image_path = tmp_path / "foo.png"
    image_path.write_bytes(_make_image_bytes())

    sample = ScreenshotSample(path=image_path, type=ScreenshotType.UNKNOWN, note="Contribution board")
    classifier = HeuristicClassifier()
    result = classifier.classify(sample)
    assert result.detected_type == ScreenshotType.CONTRIBUTION
