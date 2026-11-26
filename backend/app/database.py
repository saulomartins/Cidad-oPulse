from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import env_settings


def normalize_database_url(raw_url: str) -> str:
    """Normalize PostgreSQL URLs from Neon/Supabase/Render for SQLAlchemy + psycopg3."""
    url = (raw_url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


EFFECTIVE_DATABASE_URL = normalize_database_url(env_settings.database_url)
IS_SQLITE = EFFECTIVE_DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine = create_engine(
    EFFECTIVE_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not IS_SQLITE,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_sqlite_migrations()


def _run_sqlite_migrations():
    """Safely add newly introduced columns to existing SQLite tables without losing data."""
    if not IS_SQLITE:
        return
    with engine.begin() as conn:
        sys_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(monitored_systems)")).fetchall()}
        if "state_uf" not in sys_cols:
            conn.execute(text("ALTER TABLE monitored_systems ADD COLUMN state_uf VARCHAR(60) NOT NULL DEFAULT ''"))
        if "municipality" not in sys_cols:
            conn.execute(text("ALTER TABLE monitored_systems ADD COLUMN municipality VARCHAR(120) NOT NULL DEFAULT ''"))
        if "social_profiles_json" not in sys_cols:
            conn.execute(text("ALTER TABLE monitored_systems ADD COLUMN social_profiles_json TEXT NOT NULL DEFAULT '[]'"))

        men_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(mentions)")).fetchall()}
        if "content_type" not in men_cols:
            conn.execute(text("ALTER TABLE mentions ADD COLUMN content_type VARCHAR(30) NOT NULL DEFAULT 'mention'"))
        if "parent_post_url" not in men_cols:
            conn.execute(text("ALTER TABLE mentions ADD COLUMN parent_post_url VARCHAR(1000) NOT NULL DEFAULT ''"))
        if "sentiment_reason" not in men_cols:
            conn.execute(text("ALTER TABLE mentions ADD COLUMN sentiment_reason TEXT NOT NULL DEFAULT ''"))
        if "evidence_quote" not in men_cols:
            conn.execute(text("ALTER TABLE mentions ADD COLUMN evidence_quote TEXT NOT NULL DEFAULT ''"))

        aw_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(award_opportunities)")).fetchall()}
        if "country" not in aw_cols:
            conn.execute(text("ALTER TABLE award_opportunities ADD COLUMN country VARCHAR(100) NOT NULL DEFAULT ''"))
        if "city" not in aw_cols:
            conn.execute(text("ALTER TABLE award_opportunities ADD COLUMN city VARCHAR(120) NOT NULL DEFAULT ''"))
        if "latitude" not in aw_cols:
            conn.execute(text("ALTER TABLE award_opportunities ADD COLUMN latitude FLOAT"))
        if "longitude" not in aw_cols:
            conn.execute(text("ALTER TABLE award_opportunities ADD COLUMN longitude FLOAT"))
        if "deadline_date" not in aw_cols:
            conn.execute(text("ALTER TABLE award_opportunities ADD COLUMN deadline_date VARCHAR(20) NOT NULL DEFAULT ''"))
        if "deadline_verified_at" not in aw_cols:
            conn.execute(text("ALTER TABLE award_opportunities ADD COLUMN deadline_verified_at DATETIME"))
        if "deadline_source_note" not in aw_cols:
            conn.execute(text("ALTER TABLE award_opportunities ADD COLUMN deadline_source_note TEXT NOT NULL DEFAULT ''"))
