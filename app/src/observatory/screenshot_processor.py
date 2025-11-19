"""Auto-processing for uploaded screenshots."""
from __future__ import annotations

import logging
import pytz
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .db import models
from .ocr.ai_client import OpenAIVisionExtractor
from .ocr.timestamp_extractor import extract_timestamp

logger = logging.getLogger(__name__)


class ScreenshotProcessor:
    """Processes screenshots and saves data to database."""

    def __init__(self, alliance_id: int = 1):
        self.alliance_id = alliance_id
        self.extractor = OpenAIVisionExtractor(model="gpt-4o-mini")

    def detect_screenshot_type(self, image_path: Path) -> dict[str, Any]:
        """
        Detect what type of screenshot this is by analyzing the image.

        Returns dict with:
            - type: one of alliance_members, bear_damage, bear_overview,
                   foundry_signup, foundry_result, ac_signup,
                   contribution, alliance_power, unknown
            - confidence: float 0.0-1.0
            - method: "ai", "heuristic", or "fallback"
        """
        # First try heuristic detection based on filename
        heuristic_result = self._detect_type_heuristic(image_path)

        # Use AI to detect screenshot type
        try:
            from openai import OpenAI
            import base64
            import json
            import os

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            with image_path.open("rb") as fh:
                img_b64 = base64.b64encode(fh.read()).decode("utf-8")

            detection_prompt = """
You are analyzing a screenshot from the mobile game Whiteout Survival.

Identify which type of screen this is from the following options:

1. "alliance_members" - Shows alliance member list with player names, power (e.g., 193.2M), and furnace levels (FC1-FC9 or 25-30)
2. "bear_overview" - IMPORTANT: Shows "Hunt successful!" message with "[Hunting Trap 1]" or "[Hunting Trap 2]", includes "Rallies: XX" and "Total Alliance Damage:" numbers. This is the COMPLETION/SUCCESS screen.
3. "bear_damage" - Shows "Trap 1 Damage Rewards" or "Trap 2 Damage Rewards" title with individual player damage rankings. This is the REWARDS screen (different from overview).
4. "foundry_signup" - Shows "Legion 1 Combatants" or "Legion 2 Combatants" with signup list
5. "foundry_result" - Shows "Personal Arsenal Points" with player rankings and scores
6. "ac_signup" - Shows Alliance Championship signup screen with lanes and "Order of Battle"
7. "contribution" - Shows "Contribution Rankings" with "Daily Contribution" or "Weekly Contribution"
8. "alliance_power" - Shows alliance power rankings with alliance names and total power
9. "unknown" - None of the above

IMPORTANT: Check for "Hunt successful!" and "Rallies:" to identify bear_overview. Check for "Damage Rewards" to identify bear_damage.

Return ONLY a JSON object with two fields:
{"type": "alliance_members", "confidence": 0.95}

Where confidence is a number between 0.0 (not sure) and 1.0 (very confident).

No extra commentary.
"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": detection_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }],
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            detected_type = result.get("type", "unknown")
            confidence = result.get("confidence", 0.8)

            logger.info(f"AI detected screenshot type: {detected_type} (confidence: {confidence:.2f}) for {image_path.name}")

            # If AI is uncertain and heuristic has a strong signal, use heuristic
            if confidence < 0.7 and heuristic_result["confidence"] > 0.8:
                logger.info(f"Using heuristic result instead: {heuristic_result['type']}")
                return heuristic_result

            return {
                "type": detected_type,
                "confidence": float(confidence),
                "method": "ai"
            }

        except Exception as e:
            logger.error(
                f"AI classification failed for {image_path.name}: {type(e).__name__}: {e}",
                extra={
                    "filename": image_path.name,
                    "error_type": type(e).__name__,
                    "fallback_method": "heuristic"
                }
            )
            logger.info(f"Falling back to heuristic detection for {image_path.name}")
            return heuristic_result

    def _detect_type_heuristic(self, image_path: Path) -> dict[str, Any]:
        """
        Heuristic-based screenshot type detection using filename patterns.

        Returns dict with type, confidence, and method.
        """
        filename = image_path.name.lower()

        # Check filename patterns
        if "alliance" in filename and "member" in filename:
            return {"type": "alliance_members", "confidence": 0.85, "method": "heuristic"}

        if "bear" in filename:
            if "overview" in filename or "success" in filename:
                return {"type": "bear_overview", "confidence": 0.85, "method": "heuristic"}
            elif "damage" in filename or "reward" in filename:
                return {"type": "bear_damage", "confidence": 0.85, "method": "heuristic"}
            else:
                return {"type": "bear_damage", "confidence": 0.6, "method": "heuristic"}

        if "foundry" in filename:
            if "signup" in filename or "combatant" in filename:
                return {"type": "foundry_signup", "confidence": 0.85, "method": "heuristic"}
            elif "result" in filename or "arsenal" in filename:
                return {"type": "foundry_result", "confidence": 0.85, "method": "heuristic"}
            else:
                return {"type": "foundry_result", "confidence": 0.6, "method": "heuristic"}

        if ("ac" in filename or "championship" in filename) and ("signup" in filename or "lane" in filename):
            return {"type": "ac_signup", "confidence": 0.85, "method": "heuristic"}

        if "contribution" in filename:
            return {"type": "contribution", "confidence": 0.85, "method": "heuristic"}

        if "alliance" in filename and "power" in filename:
            return {"type": "alliance_power", "confidence": 0.85, "method": "heuristic"}

        # Default: unknown with low confidence
        return {"type": "unknown", "confidence": 0.1, "method": "heuristic"}

    def process_screenshot(
        self,
        session: Session,
        image_path: Path,
        screenshot_type: str | None = None
    ) -> dict[str, Any]:
        """
        Process a screenshot and save to database.

        Args:
            session: Database session
            image_path: Path to screenshot
            screenshot_type: Optional type override (auto-detect if None)

        Returns:
            Dict with processing results
        """
        # Detect type if not provided
        detection_result = None
        if not screenshot_type:
            detection_result = self.detect_screenshot_type(image_path)
            screenshot_type = detection_result["type"]

        # Extract timestamp
        timestamp = extract_timestamp(image_path)
        if not timestamp:
            # Use timezone-aware UTC datetime to avoid comparison errors
            timestamp = datetime.now(pytz.UTC)

        result = {
            "filename": image_path.name,
            "type": screenshot_type,
            "timestamp": timestamp.isoformat(),
            "success": False,
            "message": "",
            "records_saved": 0
        }

        # Include detection metadata if available
        if detection_result:
            result["confidence"] = detection_result.get("confidence", 0.0)
            result["detection_method"] = detection_result.get("method", "unknown")

        try:
            if screenshot_type == "alliance_members":
                records = self._process_alliance_members(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} alliance member(s)"

            elif screenshot_type == "bear_damage":
                records = self._process_bear_damage(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} bear damage score(s)"

            elif screenshot_type == "foundry_signup":
                records = self._process_foundry_signup(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} foundry signup(s)"

            elif screenshot_type == "foundry_result":
                records = self._process_foundry_result(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} foundry result(s)"

            elif screenshot_type == "ac_signup":
                records = self._process_ac_signup(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} AC signup(s)"

            elif screenshot_type == "contribution":
                records = self._process_contribution(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} contribution record(s)"

            elif screenshot_type == "alliance_power":
                records = self._process_alliance_power(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} alliance power record(s)"

            elif screenshot_type == "bear_overview":
                records = self._process_bear_overview(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"✓ Saved {records} bear overview record(s)"

            else:
                result["message"] = f"⚠ Unknown or unsupported screenshot type: {screenshot_type}"
                logger.warning(
                    f"Unknown screenshot type for {image_path.name}: {screenshot_type}",
                    extra={
                        "filename": image_path.name,
                        "screenshot_type": screenshot_type,
                        "alliance_id": self.alliance_id
                    }
                )

        except ImportError as e:
            logger.error(
                f"Missing dependency for {screenshot_type}: {e}",
                extra={
                    "filename": image_path.name,
                    "screenshot_type": screenshot_type,
                    "error_type": "ImportError",
                    "alliance_id": self.alliance_id
                }
            )
            result["message"] = f"✗ System error: Missing required component ({e}). Please contact support."

        except ValueError as e:
            logger.error(
                f"Data validation failed for {image_path.name}: {e}",
                extra={
                    "filename": image_path.name,
                    "screenshot_type": screenshot_type,
                    "error_type": "ValueError",
                    "alliance_id": self.alliance_id
                }
            )
            result["message"] = f"✗ Data extraction failed: {str(e)}. Screenshot may be cropped or unclear."

        except Exception as e:
            error_type = type(e).__name__
            logger.error(
                f"Failed to process {image_path.name}: {error_type}: {e}",
                extra={
                    "filename": image_path.name,
                    "screenshot_type": screenshot_type,
                    "error_type": error_type,
                    "alliance_id": self.alliance_id
                },
                exc_info=True
            )
            # Provide user-friendly error messages based on error type
            if "API" in str(e) or "openai" in str(e).lower():
                result["message"] = f"✗ OCR service temporarily unavailable. Please try again in a few minutes."
            elif "database" in str(e).lower() or "sqlite" in str(e).lower():
                result["message"] = f"✗ Database error. Please try again or contact support if the problem persists."
            else:
                result["message"] = f"✗ Processing failed: {str(e)}"

        # Delete screenshot after successful processing if configured
        if result["success"] and self._should_delete_screenshot():
            self._delete_screenshot(image_path)

        return result

    def _should_delete_screenshot(self) -> bool:
        """Check if screenshots should be deleted after processing."""
        from .settings import settings
        return settings.delete_successful_screenshots

    def _delete_screenshot(self, image_path: Path) -> None:
        """Delete a screenshot file after successful processing."""
        try:
            if image_path.exists():
                image_path.unlink()
                logger.info(
                    f"Deleted processed screenshot: {image_path.name}",
                    extra={
                        "filename": image_path.name,
                        "alliance_id": self.alliance_id
                    }
                )
        except Exception as e:
            logger.warning(
                f"Failed to delete screenshot {image_path.name}: {e}",
                extra={
                    "filename": image_path.name,
                    "error_type": type(e).__name__,
                    "alliance_id": self.alliance_id
                }
            )

    def _process_alliance_members(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process alliance members screenshot."""
        from .db.operations import save_alliance_members_ocr

        data = self.extractor.extract_players(image_path)
        result = save_alliance_members_ocr(session, self.alliance_id, data, timestamp)
        return result.get("players_updated", 0)

    def _process_bear_damage(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process bear damage screenshot."""
        from .db.bear_operations import save_bear_event_ocr

        data = self.extractor.extract_bear_event(image_path)
        trap_id = data.get("trap_id", 1)
        players = data.get("players", [])

        # Use timestamp as event start time
        result = save_bear_event_ocr(
            session,
            self.alliance_id,
            trap_id,
            timestamp,
            players,
            timestamp,
            screenshot_filename=image_path.name
        )
        return len(players)

    def _process_foundry_signup(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process foundry signup screenshot."""
        from .db.foundry_operations import save_foundry_signup_ocr

        data = self.extractor.extract_foundry_signup(image_path)
        legion_number = data.get("legion_number", 1)
        # Estimate event date as next Sunday from timestamp
        from datetime import timedelta
        days_until_sunday = (6 - timestamp.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        event_date = timestamp + timedelta(days=days_until_sunday)

        result = save_foundry_signup_ocr(
            session, self.alliance_id, legion_number, event_date, data, timestamp,
            screenshot_filename=image_path.name
        )
        return result.get("signups", 0)

    def _process_foundry_result(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process foundry result screenshot."""
        from .db.foundry_operations import save_foundry_result_ocr

        data = self.extractor.extract_foundry_result(image_path)
        legion_number = data.get("legion_number", 1)
        players_data = data.get("players", [])
        # Results are from previous Sunday
        from datetime import timedelta
        days_since_sunday = (timestamp.weekday() + 1) % 7
        event_date = timestamp - timedelta(days=days_since_sunday)

        result = save_foundry_result_ocr(
            session, self.alliance_id, legion_number, event_date, players_data, timestamp,
            screenshot_filename=image_path.name
        )
        return result.get("results", 0)

    def _process_ac_signup(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process AC signup screenshot."""
        from .db.ac_operations import save_ac_signup_ocr

        data = self.extractor.extract_ac_signup(image_path)
        # Week starts on Monday
        from datetime import timedelta
        days_since_monday = timestamp.weekday()
        week_start = timestamp - timedelta(days=days_since_monday)

        result = save_ac_signup_ocr(
            session, self.alliance_id, week_start, data, timestamp,
            screenshot_filename=image_path.name
        )
        return result.get("signups", 0)

    def _process_contribution(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process contribution screenshot."""
        from .db.contribution_operations import save_contribution_snapshot_ocr

        data = self.extractor.extract_contribution(image_path)
        # Week starts on Monday
        from datetime import timedelta
        days_since_monday = timestamp.weekday()
        week_start = timestamp - timedelta(days=days_since_monday)

        result = save_contribution_snapshot_ocr(
            session, self.alliance_id, week_start, timestamp, data.get("players", []), timestamp,
            screenshot_filename=image_path.name
        )
        return result.get("snapshots", 0)

    def _process_alliance_power(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process alliance power screenshot."""
        from .db.alliance_power_operations import save_alliance_power_snapshot_ocr

        data = self.extractor.extract_alliance_power(image_path)
        result = save_alliance_power_snapshot_ocr(
            session, timestamp, data.get("alliances", []), timestamp
        )
        return result.get("snapshots", 0)

    def _process_bear_overview(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process bear overview screenshot (Tesseract-based)."""
        from .db.bear_operations import find_or_create_bear_event
        from .ocr.bear_overview_parser import parse_bear_overview
        from PIL import Image

        try:
            import pytesseract
        except ImportError as e:
            logger.error(
                f"Tesseract/pytesseract not available: {e}",
                extra={
                    "filename": image_path.name,
                    "screenshot_type": "bear_overview",
                    "alliance_id": self.alliance_id
                }
            )
            raise ImportError("Tesseract OCR is not installed or configured") from e

        try:
            # Extract text using Tesseract
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)

            logger.debug(
                f"Tesseract extracted {len(text)} characters from {image_path.name}",
                extra={
                    "filename": image_path.name,
                    "text_length": len(text),
                    "alliance_id": self.alliance_id
                }
            )

        except Exception as e:
            logger.error(
                f"Tesseract extraction failed for {image_path.name}: {e}",
                extra={
                    "filename": image_path.name,
                    "error_type": type(e).__name__,
                    "alliance_id": self.alliance_id
                }
            )
            raise ValueError("Failed to extract text from screenshot") from e

        # Parse the overview data
        data = parse_bear_overview(text)

        # Save to database if we have required fields
        if data.get("trap_id"):
            find_or_create_bear_event(
                session,
                self.alliance_id,
                trap_id=data["trap_id"],
                started_at=timestamp,
                rally_count=data.get("rally_count"),
                total_damage=data.get("total_damage"),
            )
            session.commit()
            logger.info(
                f"Saved bear overview: Trap {data['trap_id']}, {data.get('rally_count', 'N/A')} rallies, "
                f"{data.get('total_damage', 'N/A')} damage",
                extra={
                    "filename": image_path.name,
                    "trap_id": data["trap_id"],
                    "rally_count": data.get("rally_count"),
                    "total_damage": data.get("total_damage"),
                    "alliance_id": self.alliance_id
                }
            )
            return 1
        else:
            logger.warning(
                f"Could not extract trap_id from bear overview: {image_path.name}",
                extra={
                    "filename": image_path.name,
                    "extracted_data": data,
                    "alliance_id": self.alliance_id
                }
            )
            raise ValueError("Could not identify trap number from screenshot. Please ensure the 'Hunt successful!' message is visible.")
