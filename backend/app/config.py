from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CidadãoPulse"
    database_url: str = f"sqlite:///{(DATA_DIR / 'cidadao_pulse.db').as_posix()}"

    # Optional access password & Google (Gmail) OAuth for public/cloud deployment
    app_password: str = ""
    google_client_id: str = ""
    admin_google_emails: str = ""
    allowed_google_emails: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # Gemini AI & Google Search Grounding
    gemini_api_key: str = ""
    gemini_model: str = "gemini-4-hydrogen"

    # Optional pluggable social connectors
    youtube_api_key: str = ""
    apify_token: str = ""
    x_bearer_token: str = ""
    meta_access_token: str = ""

    # Scheduler defaults
    awards_cron_day: str = "mon"  # mon, tue, wed, thu, fri, sat, sun
    awards_cron_hour: int = 8
    awards_cron_minute: int = 0
    sentiment_interval_hours: int = 12
    scheduler_enabled: bool = True

    # Alerts: Webhook (Slack, Teams, Generic)
    webhook_url: str = ""
    webhook_provider: str = "slack"  # slack | teams | generic

    # Alerts: SMTP Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    alert_email_to: str = ""


env_settings = Settings()

# Mapping between DB setting keys and env_settings attribute names
SETTING_KEYS: dict[str, tuple[str, bool]] = {
    # key: (env_attr, is_secret)
    "gemini_api_key": ("gemini_api_key", True),
    "gemini_model": ("gemini_model", False),
    "youtube_api_key": ("youtube_api_key", True),
    "apify_token": ("apify_token", True),
    "x_bearer_token": ("x_bearer_token", True),
    "meta_access_token": ("meta_access_token", True),
    "awards_cron_day": ("awards_cron_day", False),
    "awards_cron_hour": ("awards_cron_hour", False),
    "awards_cron_minute": ("awards_cron_minute", False),
    "sentiment_interval_hours": ("sentiment_interval_hours", False),
    "scheduler_enabled": ("scheduler_enabled", False),
    "webhook_url": ("webhook_url", True),
    "webhook_provider": ("webhook_provider", False),
    "smtp_host": ("smtp_host", False),
    "smtp_port": ("smtp_port", False),
    "smtp_user": ("smtp_user", False),
    "smtp_password": ("smtp_password", True),
    "smtp_from": ("smtp_from", False),
    "alert_email_to": ("alert_email_to", False),
    "app_password": ("app_password", True),
    "google_client_id": ("google_client_id", False),
    "admin_google_emails": ("admin_google_emails", False),
    "allowed_google_emails": ("allowed_google_emails", False),
}


def get_runtime_config(db_session=None) -> dict[str, Any]:
    """Return effective configuration combining .env defaults and DB overrides."""
    config: dict[str, Any] = {}
    for key, (attr, _) in SETTING_KEYS.items():
        config[key] = getattr(env_settings, attr)

    # Also check standard GOOGLE_API_KEY fallback if GEMINI_API_KEY is empty
    if not config["gemini_api_key"]:
        config["gemini_api_key"] = os.getenv("GOOGLE_API_KEY", "")

    if db_session is not None:
        from app.models import AppSetting

        rows = db_session.query(AppSetting).all()
        for row in rows:
            if row.key in SETTING_KEYS and row.value is not None and row.value != "":
                val: Any = row.value
                if row.key in {"awards_cron_hour", "awards_cron_minute", "sentiment_interval_hours", "smtp_port"}:
                    try:
                        val = int(row.value)
                    except ValueError:
                        pass
                elif row.key == "scheduler_enabled":
                    val = str(row.value).lower() in {"true", "1", "yes", "on"}
                config[row.key] = val

    return config


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
