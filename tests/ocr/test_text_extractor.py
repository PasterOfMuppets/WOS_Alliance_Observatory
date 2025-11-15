from __future__ import annotations

from io import BytesIO

from PIL import Image

from observatory.ocr.image_loader import load_image
from observatory.ocr.text_extractor import NoopTextExtractor, default_text_extractor


def _make_image_bytes(size=(50, 50), color=(0, 0, 0), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def test_noop_text_extractor_returns_empty() -> None:
    loaded = load_image(_make_image_bytes())
    extractor = NoopTextExtractor()
    assert extractor.extract(loaded) == ""


def test_default_text_extractor_without_binary(monkeypatch) -> None:
    monkeypatch.setattr("observatory.ocr.text_extractor.shutil.which", lambda _: None)
    loaded = load_image(_make_image_bytes())
    extractor = default_text_extractor()
    assert extractor.extract(loaded) == ""
