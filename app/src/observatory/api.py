"""FastAPI application entrypoint that orchestrates API + worker."""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import auth
from .db import models
from .db.session import get_session
from .worker import enqueue_pipeline_job, get_worker_state, start_worker, stop_worker

app = FastAPI(
    title="WOS Alliance Observatory",
    description="API + OCR worker container running inside a single image.",
    version="0.1.0",
)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Setup static files (for CSS, JS)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def startup_event() -> None:
    start_worker()


@app.on_event("shutdown")
def shutdown_event() -> None:
    stop_worker()


@app.get("/health", summary="Simple health probe")
def healthcheck() -> dict[str, object]:
    state = get_worker_state()
    return {
        "status": "ok" if state.running else "degraded",
        "processed_jobs": state.processed_jobs,
        "last_heartbeat": state.last_heartbeat,
    }


@app.get("/status/worker", summary="Worker state snapshot")
def worker_status() -> dict[str, object]:
    state = get_worker_state()
    return {
        "running": state.running,
        "processed_jobs": state.processed_jobs,
        "last_heartbeat": state.last_heartbeat,
        "last_result_preview": state.last_result_preview,
    }


@app.get("/db/health", summary="Database connectivity check")
def db_health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/pipeline/enqueue", summary="Enqueue OCR pipeline job")
def pipeline_enqueue(manifest_path: str, limit: int | None = None) -> dict[str, str]:
    manifest = Path(manifest_path)
    if not manifest.exists():
        raise HTTPException(status_code=404, detail=f"Manifest not found: {manifest}")
    enqueue_pipeline_job(manifest, limit=limit)
    return {"status": "queued", "manifest": str(manifest.resolve())}


# ============================================================================
# Web UI Endpoints
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root page - redirect to login or dashboard."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/api/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(auth.get_session)
):
    """
    Authenticate user and return JWT access token.

    Args:
        form_data: OAuth2 password flow with username and password fields

    Returns:
        dict: Object containing:
            - access_token (str): JWT token for authenticated requests
            - token_type (str): Always "bearer"

    Raises:
        HTTPException 401: Invalid username or password

    Usage:
        Include the access_token in subsequent requests via Authorization header:
        Authorization: Bearer <access_token>

    Token expires after 60 minutes (configurable via ACCESS_TOKEN_EXPIRE_MINUTES).
    """
    user = auth.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user.last_login = datetime.utcnow()
    session.commit()

    # Create access token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    email: str | None = Form(None),
    session: Session = Depends(auth.get_session)
):
    """
    Create a new user account.

    Args:
        username: Unique username for login (required)
        password: User password (will be hashed with bcrypt)
        email: Optional email address for account recovery

    Returns:
        dict: Object containing:
            - message (str): Confirmation message "User created successfully"

    Raises:
        HTTPException 400: Username already registered

    Note: New users are created with is_active=True and is_admin=False.
    Use /api/login after registration to obtain an access token.
    """
    # Check if user exists
    stmt = select(models.User).where(models.User.username == username)
    existing_user = session.execute(stmt).scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Create new user
    hashed_password = auth.get_password_hash(password)
    new_user = models.User(
        username=username,
        email=email,
        password_hash=hashed_password,
        is_active=True,
        is_admin=False,
    )

    session.add(new_user)
    session.commit()

    return {"message": "User created successfully"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page - shows alliance overview."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )


@app.get("/api/me")
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    """
    Get authenticated user profile information.

    Returns:
        dict: Object containing:
            - username (str): User's login username
            - email (str|null): User's email address
            - is_admin (bool): Whether user has admin privileges
            - default_alliance_id (int|null): ID of user's default alliance

    Requires: Valid JWT token in Authorization header

    This endpoint is useful for:
    - Displaying user info in the navigation bar
    - Determining which alliance to query for data
    - Checking admin permissions for restricted features
    """
    return {
        "username": current_user.username,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "default_alliance_id": current_user.default_alliance_id,
    }


@app.get("/roster", response_class=HTMLResponse)
async def roster(request: Request):
    """Player roster page - shows current stats for all players."""
    return templates.TemplateResponse(
        "roster.html",
        {"request": request}
    )


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Upload page - bulk screenshot upload."""
    return templates.TemplateResponse(
        "upload.html",
        {"request": request}
    )


@app.get("/events/bear", response_class=HTMLResponse)
async def events_bear_page(request: Request):
    """Bear events page."""
    return templates.TemplateResponse(
        "events_bear.html",
        {"request": request}
    )


@app.get("/events/foundry", response_class=HTMLResponse)
async def events_foundry_page(request: Request):
    """Foundry events page."""
    return templates.TemplateResponse(
        "events_foundry.html",
        {"request": request}
    )


@app.get("/events/ac", response_class=HTMLResponse)
async def events_ac_page(request: Request):
    """AC events page."""
    return templates.TemplateResponse(
        "events_ac.html",
        {"request": request}
    )


@app.get("/events/contribution", response_class=HTMLResponse)
async def events_contribution_page(request: Request):
    """Contribution tracking page."""
    return templates.TemplateResponse(
        "events_contribution.html",
        {"request": request}
    )


@app.get("/api/players")
async def get_players(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get all active players for the current user's alliance.

    Returns:
        dict: Object containing:
            - players: List of player objects, each with:
                - id (int): Player database ID
                - name (str): Player display name
                - current_power (int): Most recent power value
                - current_furnace (str): Current furnace level (e.g., "FC3", "25")
                - status (str): Player status ("active", "inactive", "removed")

    Players are sorted by current_power descending (highest power first).
    Only includes players with status="active".
    """
    alliance_id = current_user.default_alliance_id or 1

    # Get all active players with current stats
    stmt = select(models.Player).where(
        models.Player.alliance_id == alliance_id,
        models.Player.status == models.PlayerStatus.ACTIVE
    ).order_by(models.Player.current_power.desc())

    players = session.execute(stmt).scalars().all()

    return {
        "players": [
            {
                "id": p.id,
                "name": p.display_name or p.name,
                "current_power": p.current_power,
                "current_furnace": p.current_furnace,
                "status": p.status.value
            }
            for p in players
        ]
    }


@app.get("/api/players/{player_id}/history")
async def player_history(
    player_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get complete historical timeline for a specific player.

    Args:
        player_id: Database ID of the player

    Returns:
        dict: Object containing:
            - power: List of {date, value} objects showing power over time
            - furnace: List of {date, value} objects showing furnace levels over time
            - bear_scores: List of bear event participations with:
                - date (str): ISO timestamp when recorded
                - score (int): Damage points scored
                - rank (int): Player's rank in event
                - trap_id (int): Which trap (1 or 2)
            - foundry_results: List of foundry participations with:
                - date (str): ISO timestamp when recorded
                - event_date (str): Date of the foundry event
                - legion_id (int): Which legion (1 or 2)
                - score (int): Arsenal points earned
                - rank (int): Player's rank in event

    All dates are in ISO 8601 format with UTC timezone.
    Lists are sorted by date (oldest to newest for power/furnace, newest to oldest for events).
    """
    # Get power history
    power_stmt = select(models.PlayerPowerHistory).where(
        models.PlayerPowerHistory.player_id == player_id
    ).order_by(models.PlayerPowerHistory.captured_at)
    power_history = session.execute(power_stmt).scalars().all()

    # Get furnace history
    furnace_stmt = select(models.PlayerFurnaceHistory).where(
        models.PlayerFurnaceHistory.player_id == player_id
    ).order_by(models.PlayerFurnaceHistory.captured_at)
    furnace_history = session.execute(furnace_stmt).scalars().all()

    # Get bear trap scores history
    bear_stmt = select(models.BearScore).where(
        models.BearScore.player_id == player_id
    ).order_by(models.BearScore.recorded_at)
    bear_scores = session.execute(bear_stmt).scalars().all()

    # Get foundry results history
    foundry_stmt = select(models.FoundryResult).where(
        models.FoundryResult.player_id == player_id
    ).order_by(models.FoundryResult.recorded_at.desc())
    foundry_results = session.execute(foundry_stmt).scalars().all()

    return {
        "power": [
            {"date": ph.captured_at.isoformat(), "value": ph.power}
            for ph in power_history
        ],
        "furnace": [
            {"date": fh.captured_at.isoformat(), "value": fh.furnace_level}
            for fh in furnace_history
        ],
        "bear_scores": [
            {
                "date": bs.recorded_at.isoformat(),
                "score": bs.score,
                "rank": bs.rank,
                "trap_id": bs.bear_event.trap_id
            }
            for bs in bear_scores
        ],
        "foundry_results": [
            {
                "date": fr.recorded_at.isoformat(),
                "event_date": fr.foundry_event.event_date.isoformat(),
                "legion_id": fr.legion_id,
                "score": fr.score,
                "rank": fr.rank
            }
            for fr in foundry_results
        ]
    }


@app.get("/api/events/bear")
async def get_bear_events(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get all bear hunting events with participant scores, organized by trap.

    Returns:
        dict: Object containing:
            - trap1: List of Trap 1 events, each with:
                - id (int): Event database ID
                - trap_id (int): Always 1
                - started_at (str): Event start time (ISO 8601 UTC)
                - rally_count (int|null): Number of rallies
                - total_damage (int|null): Total alliance damage
                - participant_count (int): Number of players who participated
                - notes (str|null): Event notes/comments
                - scores: List of player scores with:
                    - player_id (int): Player database ID
                    - player_name (str): Player display name
                    - score (int): Damage points
                    - rank (int): Player's rank
            - trap2: List of Trap 2 events (same structure as trap1)

    Events are sorted by started_at descending (most recent first).
    Scores within each event are sorted by score descending (highest damage first).

    Note: Minimum 47-hour cooldown between runs per trap.
    """
    alliance_id = current_user.default_alliance_id or 1

    # Get bear events
    stmt = select(models.BearEvent).where(
        models.BearEvent.alliance_id == alliance_id
    ).order_by(models.BearEvent.started_at.desc())

    events = session.execute(stmt).scalars().all()

    # Group events by trap_id
    trap1_events = []
    trap2_events = []

    for e in events:
        event_data = {
            "id": e.id,
            "trap_id": e.trap_id,
            "started_at": e.started_at.isoformat(),
            "ended_at": e.ended_at.isoformat() if e.ended_at else None,
            "rally_count": e.rally_count,
            "total_damage": e.total_damage,
            "participant_count": len(e.scores),
            "scores": [
                {
                    "rank": s.rank,
                    "player_name": s.player.name,
                    "score": s.score
                }
                for s in sorted(e.scores, key=lambda x: x.rank if x.rank else 999)
            ]
        }

        if e.trap_id == 1:
            trap1_events.append(event_data)
        else:
            trap2_events.append(event_data)

    return {
        "trap1_events": trap1_events,
        "trap2_events": trap2_events,
        # Keep legacy format for backward compatibility
        "events": trap1_events + trap2_events
    }


@app.patch("/api/events/bear/{event_id}")
async def update_bear_event(
    event_id: int,
    started_at: str,
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Update the start time for a bear hunting event.

    This endpoint allows correcting event timestamps after initial creation.
    Useful when screenshots were processed late or times need adjustment.

    Args:
        event_id: Database ID of the bear event to update
        started_at: New start time as ISO 8601 string (e.g., "2025-11-19T10:00:00Z")

    Returns:
        dict: Object containing:
            - success (bool): True if update successful
            - message (str): Confirmation message

    Raises:
        HTTPException 404: Bear event not found or not owned by user's alliance
        HTTPException 400: Invalid datetime format provided

    Note: Times are stored in UTC. Frontend should handle timezone conversion for display.
    """
    from datetime import datetime
    import pytz

    alliance_id = current_user.default_alliance_id or 1

    # Find the event
    stmt = select(models.BearEvent).where(
        models.BearEvent.id == event_id,
        models.BearEvent.alliance_id == alliance_id
    )
    event = session.execute(stmt).scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Bear event not found")

    # Parse and update the timestamp
    try:
        new_timestamp = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        # Ensure timezone-aware (convert naive to UTC if needed)
        if new_timestamp.tzinfo is None:
            new_timestamp = pytz.UTC.localize(new_timestamp)
        event.started_at = new_timestamp
        session.commit()
        return {"success": True, "message": "Bear event timestamp updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")


@app.get("/api/events/foundry")
async def get_foundry_events(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get all foundry events with summary statistics and top performers.

    Returns:
        dict: Object containing:
            - events: List of foundry events, each with:
                - id (int): Event database ID
                - legion_number (int): Legion assignment (1 or 2)
                - event_date (str): Event date (ISO 8601)
                - total_troop_power (int|null): Combined troop strength
                - max_participants (int|null): Maximum allowed participants
                - actual_participants (int|null): Number who participated
                - total_score (int|null): Combined arsenal points earned
                - won (bool|null): Whether the event was won
                - signups_count (int): Number of signup records
                - results_count (int): Number of result records
                - no_shows_count (int): Players who signed up but didn't participate
                - top_results: List of top 10 performers with:
                    - rank (int): Player's rank in event
                    - player_name (str): Player display name
                    - score (int): Arsenal points earned

    Events are sorted by event_date descending (most recent first).
    Use /api/events/foundry/{event_id}/results to get full participant list.
    """
    alliance_id = current_user.default_alliance_id or 1

    stmt = select(models.FoundryEvent).where(
        models.FoundryEvent.alliance_id == alliance_id
    ).order_by(models.FoundryEvent.event_date.desc())

    events = session.execute(stmt).scalars().all()

    return {
        "events": [
            {
                "id": e.id,
                "legion_number": e.legion_number,
                "event_date": e.event_date.isoformat(),
                "total_troop_power": e.total_troop_power,
                "max_participants": e.max_participants,
                "actual_participants": e.actual_participants,
                "total_score": e.total_score,
                "won": e.won,
                "signups_count": len(e.signups),
                "results_count": len(e.results),
                "no_shows_count": len(e.signups) - len(e.results) if e.signups and e.results else 0,
                "top_results": [
                    {
                        "rank": r.rank,
                        "player_name": r.player.name,
                        "score": r.score
                    }
                    for r in sorted(e.results, key=lambda x: x.rank if x.rank else 999)[:10]
                ]
            }
            for e in events
        ]
    }


@app.get("/api/events/foundry/{event_id}/results")
async def get_foundry_event_results(
    event_id: int,
    legion: int | None = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get complete results for a specific foundry event with optional legion filtering.

    This endpoint returns all participants, not just the top 10 shown in the summary.
    Useful for displaying the full leaderboard and filtering by legion assignment.

    Args:
        event_id: Database ID of the foundry event
        legion: Optional legion filter (1 or 2). If omitted, returns all participants.

    Returns:
        dict: Object containing:
            - event_id (int): Database ID of the event
            - event_date (str): Event date (ISO 8601)
            - legion_number (int): Legion assignment for this event
            - total_results (int): Number of results returned (after legion filtering)
            - results: List of all participants with:
                - rank (int): Player's rank in event
                - player_id (int): Player database ID
                - player_name (str): Player display name
                - legion_id (int): Legion assignment (1 or 2)
                - score (int): Arsenal points earned

    Results are sorted by score descending (highest to lowest).

    Raises:
        HTTPException 404: Foundry event not found
    """
    # Get the foundry event
    event = session.get(models.FoundryEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Foundry event not found")

    # Get all results
    results = event.results

    # Filter by legion if specified
    if legion is not None:
        results = [r for r in results if r.legion_id == legion]

    # Sort by score (descending)
    sorted_results = sorted(results, key=lambda x: x.score if x.score else 0, reverse=True)

    return {
        "event_id": event_id,
        "event_date": event.event_date.isoformat(),
        "legion_number": event.legion_number,
        "total_results": len(sorted_results),
        "results": [
            {
                "rank": r.rank,
                "player_id": r.player_id,
                "player_name": r.player.name,
                "legion_id": r.legion_id,
                "score": r.score
            }
            for r in sorted_results
        ]
    }


@app.get("/api/events/foundry/{event_id}/no-shows")
async def get_foundry_no_shows(
    event_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get players who signed up for a foundry event but didn't participate (no-shows).

    This endpoint identifies attendance issues by comparing signup records against
    actual results. Helps alliance leadership track commitment and identify patterns.

    Args:
        event_id: Database ID of the foundry event

    Returns:
        dict: Object containing:
            - event_id (int): Database ID of the event
            - event_date (str): Event date (ISO 8601)
            - signups_count (int): Total number of players who signed up
            - participated_count (int): Number of players who actually participated
            - no_shows_count (int): Number of players who didn't participate
            - no_shows: List of players who didn't show, each with:
                - player_id (int): Player database ID
                - player_name (str): Player display name
                - legion_id (int): Assigned legion (1 or 2)

    No-shows list is sorted alphabetically by player_name.

    Raises:
        HTTPException 404: Foundry event not found
    """
    # Get the foundry event
    event = session.get(models.FoundryEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Foundry event not found")

    # Get all player IDs who signed up
    signup_player_ids = {signup.player_id for signup in event.signups}

    # Get all player IDs who have results
    result_player_ids = {result.player_id for result in event.results}

    # Calculate no-shows (signed up but no result)
    no_show_player_ids = signup_player_ids - result_player_ids

    # Get player details for no-shows
    no_shows = []
    for signup in event.signups:
        if signup.player_id in no_show_player_ids:
            no_shows.append({
                "player_id": signup.player_id,
                "player_name": signup.player.name,
                "legion_id": signup.legion_id
            })

    return {
        "event_id": event_id,
        "event_date": event.event_date.isoformat(),
        "signups_count": len(signup_player_ids),
        "participated_count": len(result_player_ids),
        "no_shows_count": len(no_show_player_ids),
        "no_shows": sorted(no_shows, key=lambda x: x["player_name"])
    }


@app.get("/api/events/ac")
async def get_ac_events(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get all Alliance Conflict (AC) events with summary statistics.

    Returns AC events organized by week, showing signup counts and total power.
    Each event represents one AC week with lane assignments (left/middle/right).

    Returns:
        dict: Object containing:
            - events: List of AC events, each with:
                - id (int): Event database ID
                - week_start_date (str): Monday start of AC week (ISO 8601)
                - total_registered (int|null): Number of players registered
                - total_power (int|null): Combined AC power of all participants
                - signups_count (int): Number of signup records

    Events are sorted by week_start_date descending (most recent first).

    Note: AC events run weekly. Duplicate signups are prevented by unique constraint
    on (ac_event_id, player_id), with AC power updated if higher value is uploaded.
    """
    alliance_id = current_user.default_alliance_id or 1

    stmt = select(models.ACEvent).where(
        models.ACEvent.alliance_id == alliance_id
    ).order_by(models.ACEvent.week_start_date.desc())

    events = session.execute(stmt).scalars().all()

    return {
        "events": [
            {
                "id": e.id,
                "week_start_date": e.week_start_date.isoformat(),
                "total_registered": e.total_registered,
                "total_power": e.total_power,
                "signups_count": len(e.signups)
            }
            for e in events
        ]
    }


@app.get("/api/events/contribution")
async def get_contribution_snapshots(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Get weekly contribution tracking data with the latest snapshot for each week.

    This endpoint returns the most recent snapshot for each contribution week,
    showing all players and their contribution amounts. Multiple snapshots can be
    taken per week, but only the latest is returned for display.

    Returns:
        dict: Object containing:
            - weeks: List of weekly contribution periods, each with:
                - week_start (str): Monday start of contribution week (ISO 8601)
                - snapshots: List of all players from latest snapshot with:
                    - snapshot_date (str): When this snapshot was captured (ISO 8601 UTC)
                    - player_name (str): Player display name
                    - contribution (int): Contribution points accumulated
                    - rank (int|null): Player's rank in alliance (1-100)

    Weeks are sorted by week_start descending (most recent first).
    Within each week, players are sorted by rank ascending (rank 1 first).

    Note: All players are included in snapshots, not just top performers.
    Multiple screenshots can be uploaded per week; the latest one is displayed.
    """
    alliance_id = current_user.default_alliance_id or 1

    # Get unique weeks
    stmt = select(models.ContributionSnapshot.week_start_date).where(
        models.ContributionSnapshot.alliance_id == alliance_id
    ).distinct().order_by(models.ContributionSnapshot.week_start_date.desc())

    weeks = session.execute(stmt).scalars().all()

    result_weeks = []
    for w in weeks:
        # Find the most recent snapshot_date for this week
        latest_date_stmt = select(models.ContributionSnapshot.snapshot_date).where(
            models.ContributionSnapshot.alliance_id == alliance_id,
            models.ContributionSnapshot.week_start_date == w
        ).order_by(models.ContributionSnapshot.snapshot_date.desc()).limit(1)

        latest_date = session.execute(latest_date_stmt).scalar_one_or_none()

        if not latest_date:
            continue

        # Get all snapshots from the latest date only
        snapshots_stmt = select(models.ContributionSnapshot).where(
            models.ContributionSnapshot.alliance_id == alliance_id,
            models.ContributionSnapshot.week_start_date == w,
            models.ContributionSnapshot.snapshot_date == latest_date
        ).order_by(models.ContributionSnapshot.rank)

        snapshots = session.execute(snapshots_stmt).scalars().all()

        result_weeks.append({
            "week_start": w.isoformat(),
            "snapshots": [
                {
                    "snapshot_date": s.snapshot_date.isoformat(),
                    "player_name": s.player.name,
                    "contribution": s.contribution_amount,
                    "rank": s.rank
                }
                for s in snapshots
            ]
        })

    return {"weeks": result_weeks}


@app.post("/api/upload/screenshots")
async def upload_screenshots(
    files: list[UploadFile],
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """
    Bulk upload and process game screenshots with OCR extraction.

    This is the main data ingestion endpoint. It accepts multiple screenshot files,
    classifies each one, extracts data via OCR (Tesseract or OpenAI Vision API),
    and persists structured data to the database.

    Supported screenshot types:
    - ALLIANCE_MEMBERS: Player roster with power and furnace levels
    - CONTRIBUTION: Weekly contribution leaderboard
    - BEAR_EVENT: Bear trap scores and rankings
    - AC_LANES: Alliance Conflict lane assignments
    - FOUNDRY_SIGNUPS: Foundry event signups
    - FOUNDRY_RESULTS: Foundry event results

    Args:
        files: List of screenshot files (PNG/JPG, max 5MB each)

    Returns:
        dict: Object containing:
            - message (str): Summary of processing (e.g., "Processed 5 files: 4 successful, 23 records saved")
            - results: List of per-file results, each with:
                - filename (str): Original filename
                - size (int): File size in bytes
                - type (str): Detected screenshot type or "error"
                - success (bool): Whether processing succeeded
                - message (str): Success confirmation or error details
                - records_saved (int): Number of database records created

    Processing behavior:
    - Files are saved temporarily to /app/uploads
    - Screenshot type is detected via AI + heuristic classification
    - OCR is performed (OpenAI Vision API if enabled, else Tesseract)
    - Extracted data is parsed and validated
    - Database records are created/updated
    - Rate limiting delay applied between AI OCR requests (default 12s)

    Error handling:
    - Individual file failures don't stop batch processing
    - Failed files appear in results with success=false and error message
    - Successful files show records_saved count

    Configuration:
    - Set AI_OCR_ENABLED=1 to use OpenAI Vision API
    - Set AI_OCR_RATE_LIMIT_DELAY to control request spacing (default 12)
    - Requires OPENAI_API_KEY if AI_OCR_ENABLED=1

    Note: This endpoint requires authentication and uses the user's default_alliance_id.
    """
    from .screenshot_processor import ScreenshotProcessor
    from .settings import settings

    alliance_id = current_user.default_alliance_id or 1
    processor = ScreenshotProcessor(alliance_id=alliance_id)

    upload_dir = Path("/app/uploads")
    upload_dir.mkdir(exist_ok=True)

    results = []
    total_files = len(files)

    for idx, file in enumerate(files):
        # Save file
        file_path = upload_dir / file.filename
        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        # Process screenshot
        try:
            result = processor.process_screenshot(session, file_path)
            results.append({
                "filename": file.filename,
                "size": len(content),
                "type": result["type"],
                "success": result["success"],
                "message": result["message"],
                "records_saved": result["records_saved"]
            })

            # Add rate limiting delay if AI OCR is enabled and not the last file
            # Most screenshot types use AI OCR (only bear_overview uses Tesseract)
            ai_ocr_used = result["type"] != "bear_overview"
            is_last_file = (idx == total_files - 1)

            if settings.ai_ocr_enabled and ai_ocr_used and not is_last_file:
                time.sleep(settings.ai_ocr_rate_limit_delay)

        except Exception as e:
            results.append({
                "filename": file.filename,
                "size": len(content),
                "type": "error",
                "success": False,
                "message": str(e),
                "records_saved": 0
            })

    successful = sum(1 for r in results if r["success"])
    total_records = sum(r["records_saved"] for r in results)

    return {
        "message": f"Processed {len(files)} files: {successful} successful, {total_records} records saved",
        "results": results
    }
