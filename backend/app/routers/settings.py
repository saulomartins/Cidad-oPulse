from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import SETTING_KEYS, get_runtime_config, mask_secret
from app.connectors import list_connector_statuses
from app.database import get_db
from app.models import AppSetting, NotificationLog
from app.schemas import ConnectorStatusOut, NotificationLogOut, SettingsOut, SettingsUpdate
from app.services.notifier import send_notification
from app.services.scheduler import configure_scheduler_jobs, get_next_run_times

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _build_settings_out(db: Session) -> SettingsOut:
    cfg = get_runtime_config(db)
    next_runs = get_next_run_times()
    return SettingsOut(
        gemini_api_key_masked=mask_secret(str(cfg.get("gemini_api_key", ""))),
        gemini_configured=bool(cfg.get("gemini_api_key")),
        gemini_model=str(cfg.get("gemini_model", "gemini-4-hydrogen")),
        youtube_configured=bool(cfg.get("youtube_api_key")),
        apify_configured=bool(cfg.get("apify_token")),
        x_configured=bool(cfg.get("x_bearer_token")),
        meta_configured=bool(cfg.get("meta_access_token")),
        awards_cron_day=str(cfg.get("awards_cron_day", "mon")),
        awards_cron_hour=int(cfg.get("awards_cron_hour", 8)),
        awards_cron_minute=int(cfg.get("awards_cron_minute", 0)),
        sentiment_interval_hours=int(cfg.get("sentiment_interval_hours", 12)),
        scheduler_enabled=bool(cfg.get("scheduler_enabled", True)),
        webhook_configured=bool(cfg.get("webhook_url")),
        webhook_provider=str(cfg.get("webhook_provider", "slack")),
        smtp_configured=bool(cfg.get("smtp_host") and cfg.get("alert_email_to")),
        smtp_host=str(cfg.get("smtp_host", "")),
        smtp_port=int(cfg.get("smtp_port", 587)),
        smtp_user=str(cfg.get("smtp_user", "")),
        smtp_from=str(cfg.get("smtp_from", "")),
        alert_email_to=str(cfg.get("alert_email_to", "")),
        next_awards_run=next_runs["next_awards_run"],
        next_sentiment_run=next_runs["next_sentiment_run"],
    )


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return _build_settings_out(db)


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        if key not in SETTING_KEYS or val is None:
            continue
        str_val = str(val).strip()
        # Avoid overwriting secret with masked placeholder
        _, is_secret = SETTING_KEYS[key]
        if is_secret and ("****" in str_val or str_val == ""):
            continue
        existing = db.query(AppSetting).filter(AppSetting.key == key).first()
        if existing:
            existing.value = str_val
        else:
            db.add(AppSetting(key=key, value=str_val))

    db.commit()
    configure_scheduler_jobs(get_runtime_config(db))
    return _build_settings_out(db)


@router.get("/connectors", response_model=list[ConnectorStatusOut])
def get_connectors(db: Session = Depends(get_db)):
    cfg = get_runtime_config(db)
    return list_connector_statuses(cfg)


@router.post("/test-notification")
async def test_notification(db: Session = Depends(get_db)):
    cfg = get_runtime_config(db)
    results = await send_notification(
        db,
        cfg,
        title="Teste de Alerta — CidadãoPulse",
        markdown_body="Sua integração de alertas (E-mail e/ou Webhook Slack/Teams) está conectada ao CidadãoPulse.",
        highlights=[
            "Monitoramento de sentimento na web e redes sociais ativo",
            "Radar semanal mundial de premiações para atendimento ao cidadão pronto",
        ],
    )
    return {"results": results}


@router.get("/notifications", response_model=list[NotificationLogOut])
def list_notification_logs(db: Session = Depends(get_db)):
    return (
        db.query(NotificationLog)
        .order_by(NotificationLog.created_at.desc())
        .limit(30)
        .all()
    )
