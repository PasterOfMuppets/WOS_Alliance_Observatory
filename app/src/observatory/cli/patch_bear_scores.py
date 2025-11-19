"""CLI to patch bear event scores using a JSON payload."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ..db import models
from ..db.session import SessionLocal


def _load_scores(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Scores file must be a JSON list")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError("Each score entry must be an object")
        name = item.get("name")
        score = item.get("score")
        rank = item.get("rank", idx)
        if not name or score is None:
            raise ValueError("Each score entry must include at least 'name' and 'score'")

        normalized.append({"name": str(name).strip(), "score": int(score), "rank": int(rank)})
    return normalized


def _resolve_event(session, trap_id: int, event_id: int | None) -> models.BearEvent:
    if event_id is not None:
        event = session.get(models.BearEvent, event_id)
        if event is None:
            raise SystemExit(f"Bear event {event_id} not found")
        if event.trap_id != trap_id:
            raise SystemExit(f"Bear event {event_id} is for trap {event.trap_id}, not trap {trap_id}")
        return event

    stmt = (
        select(models.BearEvent)
        .where(models.BearEvent.trap_id == trap_id)
        .order_by(models.BearEvent.started_at.desc())
    )
    event = session.execute(stmt).scalars().first()
    if event is None:
        raise SystemExit(f"No bear event found for trap {trap_id}")
    return event


def _parse_recorded_at(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    # datetime.fromisoformat supports offsets (e.g., 2024-11-21T22:00:00-05:00)
    return datetime.fromisoformat(value)


def main() -> None:  # pragma: no cover - CLI entrypoint
    parser = argparse.ArgumentParser(description="Patch bear scores for an event")
    parser.add_argument("--scores-file", type=Path, required=True, help="JSON file with score entries")
    parser.add_argument("--trap-id", type=int, default=1, choices=(1, 2), help="Bear trap number")
    parser.add_argument("--event-id", type=int, default=None, help="Explicit bear event ID to patch")
    parser.add_argument(
        "--recorded-at",
        type=str,
        default=None,
        help="Optional ISO timestamp for the screenshot time (defaults to event.started_at)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Calculate updates without committing")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        event = _resolve_event(session, trap_id=args.trap_id, event_id=args.event_id)
        recorded_at = _parse_recorded_at(args.recorded_at, fallback=event.started_at)
        scores = _load_scores(args.scores_file)

        created = 0
        updated = 0
        missing_players: list[str] = []

        for entry in scores:
            stmt = select(models.Player).where(
                models.Player.alliance_id == event.alliance_id,
                models.Player.name == entry["name"],
            )
            player = session.execute(stmt).scalar_one_or_none()
            if player is None:
                missing_players.append(entry["name"])
                continue

            score_stmt = select(models.BearScore).where(
                models.BearScore.bear_event_id == event.id,
                models.BearScore.player_id == player.id,
            )
            score_row = session.execute(score_stmt).scalar_one_or_none()

            if score_row is None:
                score_row = models.BearScore(
                    bear_event_id=event.id,
                    player_id=player.id,
                    score=entry["score"],
                    rank=entry["rank"],
                    recorded_at=recorded_at,
                )
                session.add(score_row)
                created += 1
            else:
                score_row.score = entry["score"]
                score_row.rank = entry["rank"]
                score_row.recorded_at = recorded_at
                updated += 1

        if args.dry_run:
            session.rollback()
        else:
            session.commit()

        print(
            f"Patched bear event {event.id} (trap {event.trap_id}) - "
            f"{created} created, {updated} updated, {len(missing_players)} missing players"
        )
        if missing_players:
            print("Players not found in database:")
            for name in missing_players:
                print(f" - {name}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
