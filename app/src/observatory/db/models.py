"""Database models for the observatory."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base
from .enums import EventStatType, PlayerStatus, ScreenshotStatus, ScreenshotType


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    default_alliance_id: Mapped[int | None] = mapped_column(ForeignKey("alliances.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    default_alliance: Mapped["Alliance"] = relationship(foreign_keys=[default_alliance_id])


class Alliance(Base):
    __tablename__ = "alliances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    tag: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    players: Mapped[list["Player"]] = relationship(back_populates="alliance", cascade="all, delete-orphan")
    screenshots: Mapped[list["Screenshot"]] = relationship(back_populates="alliance", cascade="all, delete-orphan")
    bear_events: Mapped[list["BearEvent"]] = relationship(back_populates="alliance", cascade="all, delete-orphan")
    foundry_events: Mapped[list["FoundryEvent"]] = relationship(back_populates="alliance", cascade="all, delete-orphan")
    ac_events: Mapped[list["ACEvent"]] = relationship(back_populates="alliance", cascade="all, delete-orphan")
    contribution_snapshots: Mapped[list["ContributionSnapshot"]] = relationship(back_populates="alliance", cascade="all, delete-orphan")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("alliance_id", "name", name="uq_player_alliance_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[PlayerStatus] = mapped_column(SAEnum(PlayerStatus, name="player_status"), default=PlayerStatus.ACTIVE)
    current_power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_furnace: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    alliance: Mapped[Alliance] = relationship(back_populates="players")
    power_history: Mapped[list["PlayerPowerHistory"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    furnace_history: Mapped[list["PlayerFurnaceHistory"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    events: Mapped[list["EventStat"]] = relationship(back_populates="player", cascade="all, delete-orphan")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"), nullable=False)
    uploader: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detected_type: Mapped[ScreenshotType] = mapped_column(SAEnum(ScreenshotType, name="screenshot_type"), default=ScreenshotType.UNKNOWN)
    status: Mapped[ScreenshotStatus] = mapped_column(SAEnum(ScreenshotStatus, name="screenshot_status"), default=ScreenshotStatus.PENDING, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alliance: Mapped[Alliance] = relationship(back_populates="screenshots")


class PlayerPowerHistory(Base):
    __tablename__ = "player_power_history"
    __table_args__ = (UniqueConstraint("player_id", "captured_at", name="uq_power_capture"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    power: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    player: Mapped[Player] = relationship(back_populates="power_history")


class PlayerFurnaceHistory(Base):
    __tablename__ = "player_furnace_history"
    __table_args__ = (UniqueConstraint("player_id", "captured_at", name="uq_furnace_capture"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    furnace_level: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    player: Mapped[Player] = relationship(back_populates="furnace_history")


class EventStat(Base):
    __tablename__ = "event_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[EventStatType] = mapped_column(SAEnum(EventStatType, name="event_stat_type"), index=True)
    metric_name: Mapped[str] = mapped_column(String(64))
    metric_value: Mapped[Numeric] = mapped_column(Numeric(18, 2))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)

    player: Mapped[Player] = relationship(back_populates="events")


class AiOcrResult(Base):
    __tablename__ = "ai_ocr_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screenshot_path: Mapped[str] = mapped_column(String(512))
    model_name: Mapped[str] = mapped_column(String(64))
    card_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BearEvent(Base):
    __tablename__ = "bear_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"), index=True)
    trap_id: Mapped[int] = mapped_column(Integer)  # 1 or 2
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rally_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_damage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alliance: Mapped[Alliance] = relationship(back_populates="bear_events")
    scores: Mapped[list["BearScore"]] = relationship(back_populates="bear_event", cascade="all, delete-orphan")


class BearScore(Base):
    __tablename__ = "bear_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bear_event_id: Mapped[int] = mapped_column(ForeignKey("bear_events.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bear_event: Mapped[BearEvent] = relationship(back_populates="scores")
    player: Mapped[Player] = relationship()


class FoundryEvent(Base):
    __tablename__ = "foundry_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"), index=True)
    legion_number: Mapped[int] = mapped_column(Integer)  # 1 or 2
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total_troop_power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # For results
    won: Mapped[bool | None] = mapped_column(nullable=True)  # For results
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alliance: Mapped[Alliance] = relationship(back_populates="foundry_events")
    signups: Mapped[list["FoundrySignup"]] = relationship(back_populates="foundry_event", cascade="all, delete-orphan")
    results: Mapped[list["FoundryResult"]] = relationship(back_populates="foundry_event", cascade="all, delete-orphan")


class FoundrySignup(Base):
    __tablename__ = "foundry_signups"
    __table_args__ = (UniqueConstraint("foundry_event_id", "player_id", name="uq_foundry_signup_event_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    foundry_event_id: Mapped[int] = mapped_column(ForeignKey("foundry_events.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    foundry_power: Mapped[int] = mapped_column(Integer)
    voted: Mapped[bool] = mapped_column(default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    foundry_event: Mapped[FoundryEvent] = relationship(back_populates="signups")
    player: Mapped[Player] = relationship()


class FoundryResult(Base):
    __tablename__ = "foundry_results"
    __table_args__ = (UniqueConstraint("foundry_event_id", "player_id", name="uq_foundry_result_event_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    foundry_event_id: Mapped[int] = mapped_column(ForeignKey("foundry_events.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    foundry_event: Mapped[FoundryEvent] = relationship(back_populates="results")
    player: Mapped[Player] = relationship()


class ACEvent(Base):
    __tablename__ = "ac_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"), index=True)
    week_start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total_registered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alliance: Mapped[Alliance] = relationship(back_populates="ac_events")
    signups: Mapped[list["ACSignup"]] = relationship(back_populates="ac_event", cascade="all, delete-orphan")


class ACSignup(Base):
    __tablename__ = "ac_signups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ac_event_id: Mapped[int] = mapped_column(ForeignKey("ac_events.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    ac_power: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ac_event: Mapped[ACEvent] = relationship(back_populates="signups")
    player: Mapped[Player] = relationship()


class ContributionSnapshot(Base):
    __tablename__ = "contribution_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    week_start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    contribution_amount: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alliance: Mapped[Alliance] = relationship(back_populates="contribution_snapshots")
    player: Mapped[Player] = relationship()


class AlliancePowerSnapshot(Base):
    __tablename__ = "alliance_power_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_name: Mapped[str] = mapped_column(String(128), index=True)
    alliance_tag: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    total_power: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer, index=True)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
