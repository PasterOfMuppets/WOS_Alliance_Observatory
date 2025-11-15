"""Screenshot classifier interfaces and stub implementation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from ..db.enums import ScreenshotType
from .dataset import ScreenshotSample
from .image_loader import ImageLoaderConfig, LoadedImage, load_image


@dataclass
class ClassificationResult:
    sample: ScreenshotSample
    detected_type: ScreenshotType
    confidence: float
    loader_output: LoadedImage


class ScreenshotClassifier(ABC):
    """Abstract classifier contract."""

    @abstractmethod
    def classify(self, sample: ScreenshotSample) -> ClassificationResult:  # pragma: no cover
        raise NotImplementedError


class HeuristicClassifier(ScreenshotClassifier):
    """Very rough classifier based on keyword heuristics."""

    def __init__(self, *, loader_config: ImageLoaderConfig | None = None) -> None:
        self.loader_config = loader_config or ImageLoaderConfig()

    def classify(self, sample: ScreenshotSample) -> ClassificationResult:
        loaded = load_image(sample.path, config=self.loader_config)
        text_hints = ((sample.note or "") + sample.path.name).lower()

        detected = ScreenshotType.UNKNOWN
        confidence = 0.1

        heuristics: Iterable[tuple[str, ScreenshotType]] = (
            ("contribution", ScreenshotType.CONTRIBUTION),
            ("member", ScreenshotType.ALLIANCE_MEMBERS),
            ("lane", ScreenshotType.AC_LANES),
            ("bear", ScreenshotType.BEAR_EVENT),
        )
        for keyword, cls_type in heuristics:
            if keyword in text_hints:
                detected = cls_type
                confidence = 0.4
                break

        return ClassificationResult(
            sample=sample,
            detected_type=detected,
            confidence=confidence,
            loader_output=loaded,
        )
