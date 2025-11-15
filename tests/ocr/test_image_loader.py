from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from observatory.ocr.image_loader import ImageLoaderConfig, ImageLoaderError, load_image


def _make_image_bytes(size=(100, 50), color=(255, 0, 0), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def test_load_image_from_bytes() -> None:
    payload = _make_image_bytes()
    loaded = load_image(payload)
    assert loaded.width == 100
    assert loaded.height == 50
    assert loaded.format == "PNG"
    assert len(loaded.raw_bytes) == len(payload)
    assert len(loaded.sha256) == 64


def test_load_image_from_path(tmp_path) -> None:
    payload = _make_image_bytes()
    path = tmp_path / "sample.png"
    path.write_bytes(payload)

    loaded = load_image(path)
    assert loaded.source_path == path


def test_load_image_rejects_big_payload() -> None:
    payload = _make_image_bytes()
    cfg = ImageLoaderConfig(max_bytes=10)
    with pytest.raises(ImageLoaderError):
        load_image(payload, config=cfg)


def test_load_image_enforces_format() -> None:
    payload = _make_image_bytes(fmt="PNG")
    cfg = ImageLoaderConfig(allowed_formats=("JPEG",))
    with pytest.raises(ImageLoaderError):
        load_image(payload, config=cfg)


def test_load_image_scales_down() -> None:
    payload = _make_image_bytes(size=(4096, 4096))
    cfg = ImageLoaderConfig(max_dimensions=(512, 512))
    loaded = load_image(payload, config=cfg)
    assert loaded.width == 512
    assert loaded.height == 512
