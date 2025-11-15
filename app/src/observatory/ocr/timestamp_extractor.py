"""Extract timestamps from screenshots (filename + EXIF data)."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS
import pytz

from ..settings import settings

logger = logging.getLogger(__name__)

# Regex for screenshot filename format: Screenshot_YYYYMMDD_HHMMSS_*.jpg
FILENAME_TIMESTAMP_PATTERN = re.compile(
    r"Screenshot_(\d{8})_(\d{6})"
)


def extract_timestamp(image_path: Path) -> datetime | None:
    """
    Extract timestamp from screenshot, trying multiple methods.

    Priority:
    1. Parse from filename (Screenshot_YYYYMMDD_HHMMSS format)
    2. Read from EXIF data
    3. Return None if both fail

    The timestamp is interpreted in the configured timezone and converted to UTC.

    Args:
        image_path: Path to screenshot file

    Returns:
        datetime in UTC, or None if extraction failed
    """
    # Try filename first
    timestamp = _extract_from_filename(image_path)
    if timestamp:
        logger.debug(f"Extracted timestamp from filename: {timestamp}")
        return _localize_and_convert_utc(timestamp)

    # Fallback to EXIF
    timestamp = _extract_from_exif(image_path)
    if timestamp:
        logger.debug(f"Extracted timestamp from EXIF: {timestamp}")
        return _localize_and_convert_utc(timestamp)

    logger.warning(f"Could not extract timestamp from {image_path.name}")
    return None


def _extract_from_filename(image_path: Path) -> datetime | None:
    """
    Parse timestamp from filename like: Screenshot_20251112_114640_Whiteout Survival.jpg

    Args:
        image_path: Path to screenshot

    Returns:
        Naive datetime (no timezone) or None
    """
    match = FILENAME_TIMESTAMP_PATTERN.search(image_path.name)
    if not match:
        return None

    date_str = match.group(1)  # YYYYMMDD
    time_str = match.group(2)  # HHMMSS

    try:
        # Parse as naive datetime
        timestamp = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
        return timestamp
    except ValueError as exc:
        logger.warning(f"Failed to parse filename timestamp: {exc}")
        return None


def _extract_from_exif(image_path: Path) -> datetime | None:
    """
    Extract timestamp from EXIF data.

    Args:
        image_path: Path to screenshot

    Returns:
        Naive datetime (no timezone) or None
    """
    try:
        with Image.open(image_path) as img:
            exif_data = img.getexif()
            if not exif_data:
                return None

            # Try DateTime tag (most common)
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "DateTime":
                    # Format: "YYYY:MM:DD HH:MM:SS"
                    timestamp = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                    return timestamp

            # Try DateTimeOriginal tag
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "DateTimeOriginal":
                    timestamp = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                    return timestamp

    except Exception as exc:
        logger.warning(f"Failed to read EXIF data: {exc}")

    return None


def _localize_and_convert_utc(naive_dt: datetime) -> datetime:
    """
    Take a naive datetime, interpret it in the configured timezone, and convert to UTC.

    Args:
        naive_dt: Naive datetime (no timezone info)

    Returns:
        Timezone-aware datetime in UTC
    """
    try:
        local_tz = pytz.timezone(settings.screenshot_timezone)
        localized = local_tz.localize(naive_dt)
        utc_dt = localized.astimezone(pytz.UTC)
        return utc_dt
    except Exception as exc:
        logger.error(f"Timezone conversion failed: {exc}")
        # Fallback: treat as UTC
        return naive_dt.replace(tzinfo=pytz.UTC)
