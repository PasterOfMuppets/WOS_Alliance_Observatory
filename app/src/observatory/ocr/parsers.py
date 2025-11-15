"""Screenshot parsing interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re
from typing import Any, Mapping

from ..db.enums import ScreenshotType
from ..settings import settings
from .ai_client import OpenAIVisionExtractor
from .classifier import ClassificationResult
from .dataset import ScreenshotSample


@dataclass
class ParsedData:
    """Parsed representation of a screenshot."""

    type: ScreenshotType
    payload: Mapping[str, Any]
    raw_text: str = ""


class ScreenshotParser(ABC):
    """Base parser contract for specific screenshot types."""

    supported_types: tuple[ScreenshotType, ...] = (ScreenshotType.UNKNOWN,)

    @abstractmethod
    def parse(self, sample: ScreenshotSample, classification: ClassificationResult, text: str) -> ParsedData:  # pragma: no cover
        raise NotImplementedError


class AllianceMembersParser(ScreenshotParser):
    supported_types = (ScreenshotType.ALLIANCE_MEMBERS,)

    def __init__(self) -> None:
        self._ai_enabled = settings.ai_ocr_enabled
        self._ai_extractor: OpenAIVisionExtractor | None = None
        if self._ai_enabled:
            try:
                self._ai_extractor = OpenAIVisionExtractor(model=settings.ai_ocr_model)
            except Exception as exc:  # pragma: no cover
                logger.warning("AI OCR initialisation failed, falling back to Tesseract: %s", exc)
                self._ai_enabled = False

    def parse(self, sample: ScreenshotSample, classification: ClassificationResult, text: str) -> ParsedData:
        ai_players: list[dict[str, Any]] | None = None
        if self._ai_enabled and self._ai_extractor:
            try:
                ai_players = self._ai_extractor.extract_players(sample.path)
            except Exception as exc:  # pragma: no cover
                logger.warning("AI OCR failed for %s: %s", sample.path.name, exc)

        if ai_players:
            players = [
                {
                    "name": entry.get("name"),
                    "power_millions": entry.get("power_millions"),
                    "power": _convert_power(entry.get("power_millions")),
                    "furnace_level": entry.get("furnace_level"),
                }
                for entry in ai_players
            ]
        else:
            players = _extract_roster_entries(text)

        payload = {
            "summary": "Alliance roster screenshot",
            "pixels": {
                "width": classification.loader_output.width,
                "height": classification.loader_output.height,
            },
            "players": players,
            "note": sample.note,
            "text_preview": text[:200],
            "ai_source": bool(ai_players),
        }
        return ParsedData(type=ScreenshotType.ALLIANCE_MEMBERS, payload=payload, raw_text=text)


class ContributionParser(ScreenshotParser):
    supported_types = (ScreenshotType.CONTRIBUTION,)

    def parse(self, sample: ScreenshotSample, classification: ClassificationResult, text: str) -> ParsedData:
        payload = {
            "summary": "Contribution leaderboard",
            "confidence": classification.confidence,
            "hint": (sample.note or sample.path.name),
            "entries": _extract_ranked_entries(text),
        }
        return ParsedData(type=ScreenshotType.CONTRIBUTION, payload=payload, raw_text=text)


class BearEventParser(ScreenshotParser):
    supported_types = (ScreenshotType.BEAR_EVENT,)

    def parse(self, sample: ScreenshotSample, classification: ClassificationResult, text: str) -> ParsedData:
        payload = {
            "summary": "Bear trap event",
            "hash": classification.loader_output.sha256[:12],
            "entries": _extract_ranked_entries(text),
        }
        return ParsedData(type=ScreenshotType.BEAR_EVENT, payload=payload, raw_text=text)


class DefaultParser(ScreenshotParser):
    supported_types = (ScreenshotType.UNKNOWN, ScreenshotType.AC_LANES)

    def parse(self, sample: ScreenshotSample, classification: ClassificationResult, text: str) -> ParsedData:
        payload = {
            "summary": "Unclassified screenshot",
            "detected": classification.detected_type.value,
            "text_preview": text[:160],
        }
        return ParsedData(type=classification.detected_type, payload=payload, raw_text=text)


ENTRY_REGEX = re.compile(
    r"(?P<prefix>[\d\)\(\.\-]{0,4})\s*(?P<name>[\w\[\]()'’\-]{1,}(?:\s+[\w\[\]()'’\-]{1,})*)\s+(?P<value>\d[\d,]{2,})",
    re.UNICODE,
)


TAG_PREFIX = re.compile(r"^[\[\(]?[A-Za-z0-9]{1,4}[\]\)]\s*")


def _clean_name(name: str) -> str:
    name = TAG_PREFIX.sub("", name).strip()
    name = re.sub(r"^[\d\W_]+", "", name)
    tokens = name.split()
    while tokens and len(tokens[0]) <= 2 and tokens[0].isalpha():
        tokens.pop(0)
    name = " ".join(tokens).strip()
    if name and all(len(part) == 1 for part in name.split()) and len(name.split()) >= 3:
        name = "".join(name.split())
    return name


def _extract_ranked_entries(text: str, limit: int = 10) -> list[dict[str, str | int]]:
    entries: list[dict[str, str | int]] = []
    seen: set[tuple[str, int]] = set()
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        match = ENTRY_REGEX.search(line)
        if not match:
            continue
        name = match.group("name").strip("[]():/")
        name = _clean_name(name)
        value_str = match.group("value").replace(",", "")
        if not value_str.isdigit():
            continue
        value = int(value_str)
        key = (name.lower(), value)
        if key in seen:
            continue
        if name.lower() in {"ranking", "contribution", "rewards"}:
            continue
        seen.add(key)
        entries.append({"name": name[:64], "value": value})
        if len(entries) >= limit:
            break
    return entries


def _extract_roster_entries(text: str, limit: int = 10) -> list[dict[str, str | int]]:
    players: list[dict[str, str | int]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not any(char.isdigit() for char in line):
            continue
        parts = line.split()
        name_parts = []
        power = None
        for token in parts:
            clean = token.replace(",", "")
            if clean.isdigit():
                power = int(clean)
            else:
                token = TAG_PREFIX.sub("", token)
                name_parts.append(token)
        if not name_parts:
            continue
        name = _clean_name(" ".join(name_parts))
        players.append({"name": name[:64], "power": power})
        if len(players) >= limit:
            break
    return players


def _convert_power(power_millions: Any) -> int | None:
    if power_millions is None:
        return None
    try:
        return int(float(power_millions) * 1_000_000)
    except (TypeError, ValueError):
        return None


def build_parser_registry() -> dict[ScreenshotType, ScreenshotParser]:
    parser_instances: list[ScreenshotParser] = [
        AllianceMembersParser(),
        ContributionParser(),
        BearEventParser(),
        DefaultParser(),
    ]
    registry: dict[ScreenshotType, ScreenshotParser] = {}
    for parser in parser_instances:
        for stype in parser.supported_types:
            registry[stype] = parser
    return registry
