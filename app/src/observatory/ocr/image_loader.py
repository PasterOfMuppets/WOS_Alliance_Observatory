"""Utility helpers for loading, validating, and normalizing screenshots."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable

from PIL import Image, ImageOps


@dataclass(frozen=True)
class ImageLoaderConfig:
    """Configuration knobs for the loader."""

    max_bytes: int = 5 * 1024 * 1024  # 5 MB cap per design doc
    allowed_formats: tuple[str, ...] = ("PNG", "JPEG")
    max_dimensions: tuple[int, int] = (2560, 1440)


@dataclass(frozen=True)
class LoadedImage:
    """Container with normalized image data plus metadata."""

    image: Image.Image
    raw_bytes: bytes
    format: str
    width: int
    height: int
    sha256: str
    source_path: Path | None = None


class ImageLoaderError(ValueError):
    """Raised when the loader encounters invalid input."""


def load_image(
    source: str | Path | bytes | BinaryIO,
    *,
    config: ImageLoaderConfig | None = None,
) -> LoadedImage:
    """Load and normalize a screenshot from disk, bytes, or file-like source."""

    cfg = config or ImageLoaderConfig()
    raw_bytes, source_path = _read_source(source, cfg.max_bytes)

    try:
        with Image.open(BytesIO(raw_bytes)) as img:
            original_format = (img.format or "").upper()
            if cfg.allowed_formats and original_format not in cfg.allowed_formats:
                raise ImageLoaderError(
                    f"Unsupported image format '{original_format or 'unknown'}'; "
                    f"expected one of {cfg.allowed_formats}"
                )

            normalized = ImageOps.exif_transpose(img).convert("RGB")
            if (
                normalized.width > cfg.max_dimensions[0]
                or normalized.height > cfg.max_dimensions[1]
            ):
                normalized.thumbnail(cfg.max_dimensions, Image.Resampling.LANCZOS)
            normalized.load()
    except Image.UnidentifiedImageError as exc:  # pragma: no cover
        raise ImageLoaderError("Unable to decode image data") from exc

    digest = sha256(raw_bytes).hexdigest()
    return LoadedImage(
        image=normalized,
        raw_bytes=raw_bytes,
        format=original_format or "",
        width=normalized.width,
        height=normalized.height,
        sha256=digest,
        source_path=source_path,
    )


def _read_source(source: str | Path | bytes | BinaryIO, max_bytes: int) -> tuple[bytes, Path | None]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        data = path.read_bytes()
        return _validate_size(data, max_bytes), path

    if isinstance(source, bytes):
        return _validate_size(source, max_bytes), None

    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):  # pragma: no cover
            data = data.encode()
        return _validate_size(data, max_bytes), None

    raise ImageLoaderError(f"Unsupported source type: {type(source)!r}")


def _validate_size(data: bytes, max_bytes: int) -> bytes:
    if len(data) > max_bytes:
        raise ImageLoaderError(
            f"Image payload exceeds {max_bytes} bytes (received {len(data)} bytes)"
        )
    return data
