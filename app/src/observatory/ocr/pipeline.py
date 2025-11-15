"""OCR processing pipeline orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..db.enums import ScreenshotType
from .classifier import ClassificationResult, HeuristicClassifier, ScreenshotClassifier
from .dataset import ScreenshotSample
from .parsers import ParsedData, ScreenshotParser, build_parser_registry
from .text_extractor import TextExtractor, default_text_extractor
from .text_inference import infer_type_from_text


@dataclass
class PipelineResult:
    sample: ScreenshotSample
    classification: ClassificationResult
    parsed: ParsedData
    text: str


class OcrPipeline:
    """Coordinates classification and parsing for screenshots."""

    def __init__(
        self,
        *,
        classifier: ScreenshotClassifier | None = None,
        parser_registry: dict[ScreenshotType, ScreenshotParser] | None = None,
        text_extractor: TextExtractor | None = None,
    ) -> None:
        self.classifier = classifier or HeuristicClassifier()
        self.parser_registry = parser_registry or build_parser_registry()
        self.text_extractor = text_extractor or default_text_extractor()

    def process_sample(self, sample: ScreenshotSample) -> PipelineResult:
        classification = self.classifier.classify(sample)
        extracted_text = self.text_extractor.extract(classification.loader_output)
        refined_type = infer_type_from_text(extracted_text, classification.detected_type)
        if refined_type != classification.detected_type:
            classification.detected_type = refined_type
        parser = self.parser_registry.get(refined_type)
        if parser is None:
            parser = self.parser_registry.get(ScreenshotType.UNKNOWN)
        parsed = parser.parse(sample, classification, extracted_text)
        return PipelineResult(sample=sample, classification=classification, parsed=parsed, text=extracted_text)

    def process_many(self, samples: Iterable[ScreenshotSample]) -> Iterable[PipelineResult]:
        for sample in samples:
            yield self.process_sample(sample)
