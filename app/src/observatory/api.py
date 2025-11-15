"""FastAPI application entrypoint that orchestrates API + worker."""
from __future__ import annotations

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
    """Login endpoint - returns JWT token."""
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
    """Register a new user."""
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
    """Get current user info."""
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
    """Get all players for current user's alliance."""
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
    """Get historical data for a player (power and furnace)."""
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

    return {
        "power": [
            {"date": ph.captured_at.isoformat(), "value": ph.power}
            for ph in power_history
        ],
        "furnace": [
            {"date": fh.captured_at.isoformat(), "value": fh.furnace_level}
            for fh in furnace_history
        ]
    }


@app.get("/api/events/bear")
async def get_bear_events(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """Get all bear events with scores."""
    alliance_id = current_user.default_alliance_id or 1

    # Get bear events
    stmt = select(models.BearEvent).where(
        models.BearEvent.alliance_id == alliance_id
    ).order_by(models.BearEvent.started_at.desc())

    events = session.execute(stmt).scalars().all()

    return {
        "events": [
            {
                "id": e.id,
                "trap_id": e.trap_id,
                "started_at": e.started_at.isoformat(),
                "ended_at": e.ended_at.isoformat() if e.ended_at else None,
                "rally_count": e.rally_count,
                "total_damage": e.total_damage,
                "scores": [
                    {
                        "rank": s.rank,
                        "player_name": s.player.name,
                        "score": s.score
                    }
                    for s in sorted(e.scores, key=lambda x: x.rank if x.rank else 999)
                ]
            }
            for e in events
        ]
    }


@app.get("/api/events/foundry")
async def get_foundry_events(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """Get all foundry events with signups and results."""
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


@app.get("/api/events/ac")
async def get_ac_events(
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """Get all AC events."""
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
    """Get contribution snapshots."""
    alliance_id = current_user.default_alliance_id or 1

    # Get unique weeks
    stmt = select(models.ContributionSnapshot.week_start_date).where(
        models.ContributionSnapshot.alliance_id == alliance_id
    ).distinct().order_by(models.ContributionSnapshot.week_start_date.desc())

    weeks = session.execute(stmt).scalars().all()

    return {
        "weeks": [
            {
                "week_start": w.isoformat(),
                "snapshots": [
                    {
                        "snapshot_date": s.snapshot_date.isoformat(),
                        "player_name": s.player.name,
                        "contribution": s.contribution_amount,
                        "rank": s.rank
                    }
                    for s in session.execute(
                        select(models.ContributionSnapshot).where(
                            models.ContributionSnapshot.alliance_id == alliance_id,
                            models.ContributionSnapshot.week_start_date == w
                        ).order_by(models.ContributionSnapshot.rank)
                    ).scalars().all()
                ]
            }
            for w in weeks
        ]
    }


@app.post("/api/upload/screenshots")
async def upload_screenshots(
    files: list[UploadFile],
    current_user: models.User = Depends(auth.get_current_active_user),
    session: Session = Depends(auth.get_session)
):
    """Bulk upload screenshots for processing."""
    # TODO: Implement screenshot upload and auto-processing
    # For now, just save the files and return status

    uploaded_files = []
    for file in files:
        # Save to temp directory
        upload_dir = Path("/app/uploads")
        upload_dir.mkdir(exist_ok=True)

        file_path = upload_dir / file.filename
        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        uploaded_files.append({
            "filename": file.filename,
            "size": len(content),
            "path": str(file_path)
        })

    return {
        "message": f"Uploaded {len(files)} files",
        "files": uploaded_files
    }
