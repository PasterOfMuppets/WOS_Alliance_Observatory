"""Tests for foundry-related API endpoints to prevent regression of legion_id field."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from observatory import auth
from observatory.api import app
from observatory.db import models
from observatory.db.models import Base
from observatory.db.session import get_session


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_user(test_db: Session) -> models.User:
    """Create a mock user for authentication."""
    user = models.User(
        username="testuser",
        email="test@example.com",
        password_hash="dummy_hash",
        is_active=True,
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_alliance(test_db: Session) -> models.Alliance:
    """Create a test alliance."""
    alliance = models.Alliance(name="Test Alliance")
    test_db.add(alliance)
    test_db.commit()
    test_db.refresh(alliance)
    return alliance


@pytest.fixture
def test_players(test_db: Session, test_alliance: models.Alliance) -> list[models.Player]:
    """Create test players."""
    players = []
    for i in range(5):
        player = models.Player(
            name=f"Player{i+1}",
            alliance_id=test_alliance.id
        )
        test_db.add(player)
        players.append(player)
    test_db.commit()
    for player in players:
        test_db.refresh(player)
    return players


@pytest.fixture
def foundry_events(
    test_db: Session,
    test_alliance: models.Alliance
) -> tuple[models.FoundryEvent, models.FoundryEvent]:
    """Create two foundry events for different legions."""
    now = datetime.now(timezone.utc)

    event_legion1 = models.FoundryEvent(
        alliance_id=test_alliance.id,
        legion_number=1,
        event_date=now,
        total_troop_power=1000000,
        max_participants=10,
        actual_participants=3
    )

    event_legion2 = models.FoundryEvent(
        alliance_id=test_alliance.id,
        legion_number=2,
        event_date=now + timedelta(days=1),
        total_troop_power=900000,
        max_participants=10,
        actual_participants=2
    )

    test_db.add_all([event_legion1, event_legion2])
    test_db.commit()
    test_db.refresh(event_legion1)
    test_db.refresh(event_legion2)

    return event_legion1, event_legion2


@pytest.fixture
def foundry_signups_and_results(
    test_db: Session,
    foundry_events: tuple[models.FoundryEvent, models.FoundryEvent],
    test_players: list[models.Player]
) -> None:
    """Create foundry signups and results."""
    event_legion1, event_legion2 = foundry_events
    now = datetime.now(timezone.utc)

    # Legion 1: 4 signups, 3 results (1 no-show)
    for i in range(4):
        signup = models.FoundrySignup(
            foundry_event_id=event_legion1.id,
            player_id=test_players[i].id,
            foundry_power=50000 + i * 1000,
            voted=True,
            recorded_at=now
        )
        test_db.add(signup)

    # Add results for first 3 players (4th player is a no-show)
    for i in range(3):
        result = models.FoundryResult(
            foundry_event_id=event_legion1.id,
            player_id=test_players[i].id,
            score=1000 + i * 100,
            rank=i + 1,
            recorded_at=now
        )
        test_db.add(result)

    # Legion 2: 3 signups, 2 results (1 no-show)
    for i in range(3):
        signup = models.FoundrySignup(
            foundry_event_id=event_legion2.id,
            player_id=test_players[i].id,
            foundry_power=45000 + i * 1000,
            voted=False,
            recorded_at=now
        )
        test_db.add(signup)

    # Add results for first 2 players
    for i in range(2):
        result = models.FoundryResult(
            foundry_event_id=event_legion2.id,
            player_id=test_players[i].id,
            score=900 + i * 50,
            rank=i + 1,
            recorded_at=now
        )
        test_db.add(result)

    test_db.commit()


@pytest.fixture
def client(test_db: Session, mock_user: models.User) -> TestClient:
    """Create a test client with mocked authentication and database."""

    # Override get_session dependency to use test database
    def override_get_session() -> Generator[Session, None, None]:
        yield test_db

    # Override authentication to return mock user
    async def override_get_current_active_user() -> models.User:
        return mock_user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[auth.get_current_active_user] = override_get_current_active_user

    client = TestClient(app)
    yield client

    # Clean up overrides
    app.dependency_overrides.clear()


def test_player_history_includes_legion_id(
    client: TestClient,
    test_players: list[models.Player],
    foundry_signups_and_results: None
) -> None:
    """Test that player history endpoint includes legion_id in foundry_results."""
    player = test_players[0]

    response = client.get(f"/api/players/{player.id}/history")
    assert response.status_code == 200

    data = response.json()
    assert "foundry_results" in data
    assert len(data["foundry_results"]) > 0

    # Check that each foundry result has legion_id
    for result in data["foundry_results"]:
        assert "legion_id" in result
        assert result["legion_id"] in [1, 2]
        assert "score" in result
        assert "rank" in result
        assert "date" in result
        assert "event_date" in result


def test_foundry_results_includes_legion_id(
    client: TestClient,
    foundry_events: tuple[models.FoundryEvent, models.FoundryEvent],
    foundry_signups_and_results: None
) -> None:
    """Test that foundry results endpoint includes legion_id in each result."""
    event_legion1, _ = foundry_events

    response = client.get(f"/api/events/foundry/{event_legion1.id}/results")
    assert response.status_code == 200

    data = response.json()
    assert data["event_id"] == event_legion1.id
    assert data["legion_number"] == 1
    assert len(data["results"]) == 3

    # Check that each result has legion_id
    for result in data["results"]:
        assert "legion_id" in result
        assert result["legion_id"] == 1
        assert "player_id" in result
        assert "player_name" in result
        assert "score" in result
        assert "rank" in result


def test_foundry_results_legion_filter_matches(
    client: TestClient,
    foundry_events: tuple[models.FoundryEvent, models.FoundryEvent],
    foundry_signups_and_results: None
) -> None:
    """Test that legion filter returns results when legion matches."""
    event_legion1, _ = foundry_events

    response = client.get(f"/api/events/foundry/{event_legion1.id}/results?legion=1")
    assert response.status_code == 200

    data = response.json()
    assert data["event_id"] == event_legion1.id
    assert data["legion_number"] == 1
    assert len(data["results"]) == 3  # Should return all results


def test_foundry_results_legion_filter_no_match(
    client: TestClient,
    foundry_events: tuple[models.FoundryEvent, models.FoundryEvent],
    foundry_signups_and_results: None
) -> None:
    """Test that legion filter returns empty results when legion doesn't match."""
    event_legion1, _ = foundry_events

    # Request legion 2 results for a legion 1 event
    response = client.get(f"/api/events/foundry/{event_legion1.id}/results?legion=2")
    assert response.status_code == 200

    data = response.json()
    assert data["event_id"] == event_legion1.id
    assert data["legion_number"] == 1
    assert len(data["results"]) == 0  # Should return empty results


def test_foundry_results_no_legion_filter(
    client: TestClient,
    foundry_events: tuple[models.FoundryEvent, models.FoundryEvent],
    foundry_signups_and_results: None
) -> None:
    """Test that results are returned when no legion filter is provided."""
    event_legion2, _ = foundry_events

    response = client.get(f"/api/events/foundry/{event_legion2.id}/results")
    assert response.status_code == 200

    data = response.json()
    assert data["event_id"] == event_legion2.id
    assert data["legion_number"] == 2
    assert len(data["results"]) == 2


def test_foundry_no_shows_includes_legion_id(
    client: TestClient,
    foundry_events: tuple[models.FoundryEvent, models.FoundryEvent],
    foundry_signups_and_results: None,
    test_players: list[models.Player]
) -> None:
    """Test that no-shows endpoint includes legion_id for each no-show player."""
    event_legion1, _ = foundry_events

    response = client.get(f"/api/events/foundry/{event_legion1.id}/no-shows")
    assert response.status_code == 200

    data = response.json()
    assert data["event_id"] == event_legion1.id
    assert data["signups_count"] == 4
    assert data["participated_count"] == 3
    assert data["no_shows_count"] == 1

    # Check that the no-show entry has legion_id
    assert len(data["no_shows"]) == 1
    no_show = data["no_shows"][0]
    assert "player_id" in no_show
    assert "player_name" in no_show
    assert "legion_id" in no_show
    assert no_show["legion_id"] == 1
    assert no_show["player_id"] == test_players[3].id  # 4th player didn't participate


def test_foundry_no_shows_multiple_no_shows(
    client: TestClient,
    foundry_events: tuple[models.FoundryEvent, models.FoundryEvent],
    foundry_signups_and_results: None
) -> None:
    """Test no-shows endpoint with multiple no-shows in legion 2."""
    _, event_legion2 = foundry_events

    response = client.get(f"/api/events/foundry/{event_legion2.id}/no-shows")
    assert response.status_code == 200

    data = response.json()
    assert data["event_id"] == event_legion2.id
    assert data["signups_count"] == 3
    assert data["participated_count"] == 2
    assert data["no_shows_count"] == 1

    # All no-shows should have legion_id
    for no_show in data["no_shows"]:
        assert "legion_id" in no_show
        assert no_show["legion_id"] == 2
