"""Session and engine helpers."""
from __future__ import annotations

from sqlalchemy import create_engine
from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

from ..settings import ensure_data_dir, settings

ensure_data_dir()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)


def get_session() -> Iterator[Session]:
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
