"""AI-based OCR helpers using the OpenAI Responses API."""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

DEFAULT_PROMPT = """
You are an OCR + data extraction helper for the game Whiteout Survival.

The user will send you a screenshot of the "Alliance Members" page.

Each MEMBER CARD shows:
- Player name at the top
- Power below the name (e.g., "193.2M", "6.6M", "847K")
- Furnace level indicator (IMPORTANT - see below)
- Last online info under that (ignore for this task)

FURNACE LEVEL RULES (CRITICAL):
- Almost all furnace levels will be single digits (1-9) with a red shield icon
- Single digit numbers (1-9) should ALWAYS be formatted as "FC{number}" (e.g., "FC1", "FC3", "FC4", "FC5")
- RARE CASE: Numbers 25-30 represent non-FC furnace levels (no red shield), return as plain numbers "25", "26", etc.
- Return furnace_level as a STRING to preserve "FC" prefix

Your job:
1. Count ALL fully visible member cards.
2. For each card extract:
   - name (string)
   - power_millions (number in millions, e.g., 193.2 for 193.2M; use decimals)
   - furnace_level (string: "FC1" through "FC9" for single digits, or "25"-"30" for rare high levels)
   If any field is unreadable, set it to null but keep the card in the list.

Return ONLY JSON in this format:
{
  "card_count": <int>,
  "players": [
    {"name": "...", "power_millions": <number|null>, "furnace_level": <string|null>}
  ]
}

The length of players MUST equal card_count. No extra commentary.
"""


logger = logging.getLogger(__name__)


BEAR_EVENT_PROMPT = """
You are an OCR + data extraction helper for the game Whiteout Survival.

The user will send you a screenshot of a "Bear Trap Damage Rewards" screen.

The screen shows:
- A title indicating which trap: "Trap 1 Damage Rewards" or "Trap 2 Damage Rewards"
- A damage ranking list with player entries

Each player entry shows:
- Rank number (1, 2, 3, etc., or "Unranked")
- Player name (often with alliance tag like [HEI])
- Damage Points (large numbers with commas, e.g., "6,442,016,308")

Your job:
1. Determine the trap ID (1 or 2) from the title
2. Extract ALL visible player entries with:
   - rank (integer, or null if "Unranked")
   - name (string, keep alliance tags like [HEI])
   - damage_points (integer, remove commas)

Return ONLY JSON in this format:
{
  "trap_id": <1 or 2>,
  "players": [
    {"rank": <int|null>, "name": "...", "damage_points": <int>}
  ]
}

No extra commentary.
"""


FOUNDRY_SIGNUP_PROMPT = """
You are an OCR + data extraction helper for the game Whiteout Survival.

The user will send you a screenshot of "Legion 1 Combatants" or "Legion 2 Combatants" (Foundry signup screen).

The screen shows:
- Title: "Legion 1 Combatants" or "Legion 2 Combatants"
- Header with "Join 18/30" and "Troop Power: 34,695"
- A list of players grouped by teams (R5, R4, R3, R2)

Each player entry shows:
- Player name (e.g., "D A D D Y☭〜", "Valorin", "StrayaCat")
- Foundry power (number with icon, e.g., 2,260, 5,000, 1,752)
- Status on the RIGHT side:
  * "Join" (green) = Signed up for THIS legion
  * "Legion 2 dispatched" (green) = Signed up for the OTHER legion (Legion 2)
  * "No engagements" (gray) = Haven't signed up for either legion
- "Voted" badge (top right of card) if present

Your job:
1. Determine the legion number (1 or 2) from the title
2. Extract header stats:
   - total_troop_power (from "Troop Power: 34,695")
   - max_participants (from "Join 18/30", extract the "30")
   - actual_participants (from "Join 18/30", extract the "18")
3. For EACH player entry, extract:
   - name (string, preserve special characters)
   - foundry_power (integer, the number shown, remove commas)
   - status (string: "join", "legion_2_dispatched", "no_engagements")
   - voted (boolean: true if "Voted" badge is visible, false otherwise)

IMPORTANT: Extract ALL players visible, regardless of their status (join/no engagements/other legion).

Return ONLY JSON in this format:
{
  "legion_number": <1 or 2>,
  "total_troop_power": <int>,
  "max_participants": <int>,
  "actual_participants": <int>,
  "players": [
    {
      "name": "...",
      "foundry_power": <int>,
      "status": "join|legion_2_dispatched|no_engagements",
      "voted": <boolean>
    }
  ]
}

No extra commentary.
"""


FOUNDRY_RESULT_PROMPT = """
You are an OCR + data extraction helper for the game Whiteout Survival.

The user will send you a screenshot of "Personal Arsenal Points" (Foundry results screen).

The screen shows:
- A "Personal Arsenal Points" header (or might be scrolled to show rankings directly)
- Player rankings with rank number, player name, and arsenal points score

Each player entry shows:
- Rank number (1, 2, 3, 4, etc., shown as badges or numbers)
- Player name (e.g., "Stevie", "xBes", "Valorin", "Moensori")
- Arsenal Points score (large numbers with commas, e.g., "3,304,232", "965,171")

Your job:
1. Extract ALL visible player entries with:
   - rank (integer: 1, 2, 3, etc.)
   - name (string, preserve special characters)
   - score (integer, remove commas from arsenal points)

Return ONLY JSON in this format:
{
  "players": [
    {"rank": <int>, "name": "...", "score": <int>}
  ]
}

No extra commentary.
"""


AC_SIGNUP_PROMPT = """
You are an OCR + data extraction helper for the game Whiteout Survival.

The user will send you a screenshot of Alliance Championship (AC) signup screen.

The screen shows:
- Lane tabs at top: "Left Lane", "Middle Lane", "Right Lane" (ignore which lane)
- Header with "Registered: 20/20" and "Power: 70,037"
- A list of players with "Order of Battle" numbers and AC power

Each player entry shows:
- Order number (on left, e.g., 20, 19, 18) - IGNORE THIS, don't extract
- Player name (e.g., "[HEI]-✝-WRATH-✝-", "[HEI]xBes", "[HEI]Jayy")
- Power (e.g., "Power: 5,034", "Power: 4,924")

Your job:
1. Extract header stats:
   - total_registered (from "Registered: 20/20", extract total - the second number)
   - total_power (from "Power: 70,037")
2. For EACH player entry, extract:
   - name (string, preserve all characters including alliance tags and special symbols)
   - ac_power (integer, from "Power: X,XXX", remove commas)

IMPORTANT: Extract ALL visible players, regardless of their order number.

Return ONLY JSON in this format:
{
  "total_registered": <int>,
  "total_power": <int>,
  "players": [
    {
      "name": "...",
      "ac_power": <int>
    }
  ]
}

No extra commentary.
"""


CONTRIBUTION_PROMPT = """
You are an OCR + data extraction helper for the game Whiteout Survival.

The user will send you a screenshot of "Alliance Ranking" → "Contribution Rankings" screen.

The screen shows:
- Tabs at top: "Power Rankings", "KO Rankings", "Contribution Rankings" (currently on Contribution)
- Sub-tabs: "Daily Contribution" / "Weekly Contribution" (could be either)
- A list of players with rankings and contribution amounts

Each player entry shows:
- Rank number (1, 2, 3, ... 94, 95, etc.)
- Player name (e.g., "JasonX", "jack275", "D A D D Y☭〜")
- Contribution amount (e.g., 83,760, 81,600, 0)

Your job:
Extract ALL visible player entries with:
- rank (integer: 1, 2, 3, etc.)
- name (string, preserve special characters)
- contribution (integer, remove commas)

Return ONLY JSON in this format:
{
  "players": [
    {"rank": <int>, "name": "...", "contribution": <int>}
  ]
}

No extra commentary.
"""


ALLIANCE_POWER_PROMPT = """
You are an OCR + data extraction helper for the game Whiteout Survival.

The user will send you a screenshot of "Alliance Power" rankings screen.

The screen shows:
- A list of alliances with their ranks and total power

Each alliance entry shows:
- Rank number (1, 2, 3, etc.)
- Alliance name with tag (e.g., "[KIL]ShadowWarriors", "[HEI]HellImperium", "[ONE]MVP")
- Total power (large numbers with commas, e.g., "19,237,434,928", "17,479,324,213")

Your job:
Extract ALL visible alliance entries with:
- rank (integer: 1, 2, 3, etc.)
- alliance_name_with_tag (string, the full name including [TAG], e.g., "[KIL]ShadowWarriors")
- total_power (integer, remove commas)

Return ONLY JSON in this format:
{
  "alliances": [
    {"rank": <int>, "alliance_name_with_tag": "...", "total_power": <int>}
  ]
}

No extra commentary.
"""


from ..db.session import SessionLocal
from ..db import models


class OpenAIVisionExtractor:
    """Calls OpenAI's vision models to extract structured roster data."""

    def __init__(self, model: str = "gpt-4.1-mini", prompt: str = DEFAULT_PROMPT) -> None:
        self.model = model
        self.prompt = prompt
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set; cannot run AI OCR")
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Failed to initialise OpenAI client. Did you set OPENAI_API_KEY?") from exc

    def extract_players(self, image_path: Path) -> list[dict[str, Any]]:
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        with image_path.open("rb") as fh:
            img_b64 = base64.b64encode(fh.read()).decode("utf-8")

        try:
            response_data = self._call_openai(img_b64)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc

        # Extract JSON from chat completion response
        raw = response_data["choices"][0]["message"]["content"]
        payload = json.loads(raw)
        players = payload.get("players", [])
        card_count = payload.get("card_count")
        if card_count is not None and len(players) != card_count:
            logger.warning(
                "AI OCR card_count mismatch: %s vs players=%s", card_count, len(players)
            )
        self._persist_result(image_path, payload)
        return players

    def extract_bear_event(self, image_path: Path) -> dict[str, Any]:
        """Extract bear event data (trap ID, rankings, damage scores) from screenshot."""
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        with image_path.open("rb") as fh:
            img_b64 = base64.b64encode(fh.read()).decode("utf-8")

        try:
            response_data = self._call_openai_with_prompt(img_b64, BEAR_EVENT_PROMPT)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc

        # Extract JSON from chat completion response
        raw = response_data["choices"][0]["message"]["content"]
        payload = json.loads(raw)

        self._persist_result(image_path, payload)
        return payload

    def extract_foundry_signup(self, image_path: Path) -> dict[str, Any]:
        """Extract foundry signup data (legion, players, status, votes) from screenshot."""
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        with image_path.open("rb") as fh:
            img_b64 = base64.b64encode(fh.read()).decode("utf-8")

        try:
            response_data = self._call_openai_with_prompt(img_b64, FOUNDRY_SIGNUP_PROMPT)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc

        # Extract JSON from chat completion response
        raw = response_data["choices"][0]["message"]["content"]
        payload = json.loads(raw)

        self._persist_result(image_path, payload)
        return payload

    def extract_foundry_result(self, image_path: Path) -> dict[str, Any]:
        """Extract foundry result data (player rankings and scores) from screenshot."""
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        with image_path.open("rb") as fh:
            img_b64 = base64.b64encode(fh.read()).decode("utf-8")

        try:
            response_data = self._call_openai_with_prompt(img_b64, FOUNDRY_RESULT_PROMPT)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc

        # Extract JSON from chat completion response
        raw = response_data["choices"][0]["message"]["content"]
        payload = json.loads(raw)

        self._persist_result(image_path, payload)
        return payload

    def extract_ac_signup(self, image_path: Path) -> dict[str, Any]:
        """Extract Alliance Championship signup data (players and AC power) from screenshot."""
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        with image_path.open("rb") as fh:
            img_b64 = base64.b64encode(fh.read()).decode("utf-8")

        try:
            response_data = self._call_openai_with_prompt(img_b64, AC_SIGNUP_PROMPT)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc

        # Extract JSON from chat completion response
        raw = response_data["choices"][0]["message"]["content"]
        payload = json.loads(raw)

        self._persist_result(image_path, payload)
        return payload

    def extract_contribution(self, image_path: Path) -> dict[str, Any]:
        """Extract contribution ranking data from screenshot."""
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        with image_path.open("rb") as fh:
            img_b64 = base64.b64encode(fh.read()).decode("utf-8")

        try:
            response_data = self._call_openai_with_prompt(img_b64, CONTRIBUTION_PROMPT)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc

        # Extract JSON from chat completion response
        raw = response_data["choices"][0]["message"]["content"]
        payload = json.loads(raw)

        self._persist_result(image_path, payload)
        return payload

    def extract_alliance_power(self, image_path: Path) -> dict[str, Any]:
        """Extract alliance power ranking data from screenshot."""
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        with image_path.open("rb") as fh:
            img_b64 = base64.b64encode(fh.read()).decode("utf-8")

        try:
            response_data = self._call_openai_with_prompt(img_b64, ALLIANCE_POWER_PROMPT)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc

        # Extract JSON from chat completion response
        raw = response_data["choices"][0]["message"]["content"]
        payload = json.loads(raw)

        self._persist_result(image_path, payload)
        return payload

    def _persist_result(self, image_path: Path, payload: dict[str, Any]) -> None:
        result = models.AiOcrResult(
            screenshot_path=str(image_path),
            model_name=self.model,
            card_count=payload.get("card_count"),
            payload=payload,
        )
        with SessionLocal() as session:
            session.add(result)
            session.commit()

    def _call_openai(self, img_b64: str) -> dict[str, Any]:
        return self._call_openai_with_prompt(img_b64, self.prompt)

    def _call_openai_with_prompt(self, img_b64: str, prompt: str) -> dict[str, Any]:
        # Use the standard chat completions API for vision
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )
        return response.model_dump()
