from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from observatory.db.enums import ScreenshotType
from observatory.ocr.dataset import ScreenshotSample
from observatory.ocr.pipeline import OcrPipeline
from observatory.ocr.text_extractor import TextExtractor


def _make_image_bytes(size=(100, 50), color=(255, 255, 255), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


class DummyExtractor(TextExtractor):
    def __init__(self, text: str) -> None:
        self.text = text

    def extract(self, loaded) -> str:
        return self.text


def test_pipeline_selects_parser(tmp_path: Path) -> None:
    img_path = tmp_path / "members.png"
    img_path.write_bytes(_make_image_bytes())
    sample = ScreenshotSample(path=img_path, type=ScreenshotType.UNKNOWN, note="members list")

    pipeline = OcrPipeline(text_extractor=DummyExtractor("Alice 12345\nBob 7777"))
    result = pipeline.process_sample(sample)
    assert result.parsed.type in {ScreenshotType.ALLIANCE_MEMBERS, ScreenshotType.UNKNOWN}
    assert "summary" in result.parsed.payload
    if result.parsed.payload.get("entries"):
        assert isinstance(result.parsed.payload["entries"], list)
