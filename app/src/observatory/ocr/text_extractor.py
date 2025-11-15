"""Text extraction helpers for OCR pipeline."""
from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod

from PIL import Image, ImageOps

try:  # pragma: no cover
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore

from .image_loader import LoadedImage

logger = logging.getLogger(__name__)


class TextExtractor(ABC):
    """Abstract text extractor interface."""

    @abstractmethod
    def extract(self, loaded: LoadedImage) -> str:
        raise NotImplementedError


class NoopTextExtractor(TextExtractor):
    """Fallback extractor that returns empty text."""

    def extract(self, loaded: LoadedImage) -> str:  # noqa: D401
        return ""


class TesseractTextExtractor(TextExtractor):
    """Wrapper around pytesseract with primary + secondary passes."""

    def __init__(
        self,
        *,
        lang_primary: str = "eng+chi_sim+chi_tra+ara",
        psm_primary: int = 6,
        lang_secondary: str | None = None,
        psm_secondary: int | None = 4,
    ) -> None:
        self.lang_primary = lang_primary
        self.lang_secondary = lang_secondary or lang_primary
        self.psm_primary = psm_primary
        self.psm_secondary = psm_secondary
        self._binary_available = bool(shutil.which("tesseract"))
        if pytesseract is None or not self._binary_available:
            logger.warning("Tesseract binary or pytesseract missing; text extraction disabled")

    def _run_ocr(self, image: Image.Image, *, lang: str, psm: int) -> str:
        config = f"--psm {psm}"
        return pytesseract.image_to_string(image, lang=lang, config=config)

    def extract(self, loaded: LoadedImage) -> str:
        if pytesseract is None or not self._binary_available:
            return ""
        try:
            img = ImageOps.autocontrast(loaded.image.convert("L"))
            primary = self._run_ocr(img, lang=self.lang_primary, psm=self.psm_primary)
            secondary = ""
            if self.psm_secondary is not None:
                secondary = self._run_ocr(img, lang=self.lang_secondary, psm=self.psm_secondary)
            return primary + ("\n" + secondary if secondary else "")
        except Exception as exc:  # pragma: no cover
            logger.warning("Tesseract failed: %s", exc)
            return ""


def default_text_extractor() -> TextExtractor:
    if pytesseract is None or not shutil.which("tesseract"):
        return NoopTextExtractor()
    return TesseractTextExtractor()
