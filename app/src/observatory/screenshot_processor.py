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

    def detect_screenshot_type(self, image_path: Path) -> str:
        """
        Detect what type of screenshot this is by analyzing the image.

        Returns one of: alliance_members, bear_damage, bear_overview,
                       foundry_signup, foundry_result, ac_signup,
                       contribution, alliance_power, unknown
        """
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

Return ONLY a JSON object with one field:
{"type": "alliance_members"}

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
            logger.info(f"Detected screenshot type: {detected_type} for {image_path.name}")
            return detected_type

        except Exception as e:
            logger.error(f"Failed to detect screenshot type: {e}")
            return "unknown"

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
        if not screenshot_type:
            screenshot_type = self.detect_screenshot_type(image_path)

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

        try:
            if screenshot_type == "alliance_members":
                records = self._process_alliance_members(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} alliance members"

            elif screenshot_type == "bear_damage":
                records = self._process_bear_damage(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} bear damage scores"

            elif screenshot_type == "foundry_signup":
                records = self._process_foundry_signup(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} foundry signups"

            elif screenshot_type == "foundry_result":
                records = self._process_foundry_result(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} foundry results"

            elif screenshot_type == "ac_signup":
                records = self._process_ac_signup(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} AC signups"

            elif screenshot_type == "contribution":
                records = self._process_contribution(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} contribution records"

            elif screenshot_type == "alliance_power":
                records = self._process_alliance_power(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} alliance power records"

            elif screenshot_type == "bear_overview":
                records = self._process_bear_overview(session, image_path, timestamp)
                result["records_saved"] = records
                result["success"] = True
                result["message"] = f"Saved {records} bear overview records"

            else:
                result["message"] = f"Unknown screenshot type: {screenshot_type}"

        except Exception as e:
            logger.error(f"Failed to process {image_path.name}: {e}")
            result["message"] = f"Error: {str(e)}"

        return result

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
            timestamp
        )
        return len(players)

    def _process_foundry_signup(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process foundry signup screenshot."""
        from .db.foundry_operations import save_foundry_signup_ocr

        data = self.extractor.extract_foundry_signup(image_path)
        # Estimate event date as next Sunday from timestamp
        from datetime import timedelta
        days_until_sunday = (6 - timestamp.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        event_date = timestamp + timedelta(days=days_until_sunday)

        result = save_foundry_signup_ocr(
            session, self.alliance_id, data, event_date, timestamp
        )
        return result.get("signups", 0)

    def _process_foundry_result(self, session: Session, image_path: Path, timestamp: datetime) -> int:
        """Process foundry result screenshot."""
        from .db.foundry_operations import save_foundry_result_ocr

        data = self.extractor.extract_foundry_result(image_path)
        # Results are from previous Sunday
        from datetime import timedelta
        days_since_sunday = (timestamp.weekday() + 1) % 7
        event_date = timestamp - timedelta(days=days_since_sunday)

        result = save_foundry_result_ocr(
            session, self.alliance_id, 1, data, event_date, timestamp
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
            session, self.alliance_id, data, week_start, timestamp
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
            session, self.alliance_id, week_start, timestamp, data.get("players", []), timestamp
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
        import pytesseract
        from PIL import Image

        # Extract text using Tesseract
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)

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
            return 1

        return 0
