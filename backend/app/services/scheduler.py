from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_runtime_config
from app.database import SessionLocal
from app.services.monitor_runner import run_awards_radar_job, run_sentiment_scan

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")


async def _scheduled_awards_task():
    db = SessionLocal()
    try:
        logger.info("Running scheduled weekly awards radar job...")
        await run_awards_radar_job(db, trigger="scheduled")
    finally:
        db.close()


async def _scheduled_sentiment_task():
    db = SessionLocal()
    try:
        logger.info("Running scheduled sentiment monitoring job...")
        await run_sentiment_scan(db, trigger="scheduled")
    finally:
        db.close()


def configure_scheduler_jobs(runtime_config: dict[str, Any] | None = None):
    if runtime_config is None:
        db = SessionLocal()
        try:
            runtime_config = get_runtime_config(db)
        finally:
            db.close()

    for job_id in ("weekly_awards_radar", "periodic_sentiment_scan"):
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

    if not runtime_config.get("scheduler_enabled", True):
        logger.info("Scheduler disabled by configuration.")
        return

    day_of_week = str(runtime_config.get("awards_cron_day", "mon") or "mon").lower()
    hour = int(runtime_config.get("awards_cron_hour", 8) or 8)
    minute = int(runtime_config.get("awards_cron_minute", 0) or 0)
    interval_hours = max(1, int(runtime_config.get("sentiment_interval_hours", 12) or 12))

    scheduler.add_job(
        _scheduled_awards_task,
        CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone="America/Sao_Paulo"),
        id="weekly_awards_radar",
        replace_existing=True,
    )
    scheduler.add_job(
        _scheduled_sentiment_task,
        IntervalTrigger(hours=interval_hours),
        id="periodic_sentiment_scan",
        replace_existing=True,
    )
    logger.info(
        "Scheduler configured: weekly awards on %s %02d:%02d; sentiment every %dh.",
        day_of_week,
        hour,
        minute,
        interval_hours,
    )


def get_next_run_times() -> dict[str, str | None]:
    awards_job = scheduler.get_job("weekly_awards_radar") if scheduler.running else None
    sentiment_job = scheduler.get_job("periodic_sentiment_scan") if scheduler.running else None
    return {
        "next_awards_run": awards_job.next_run_time.isoformat() if awards_job and awards_job.next_run_time else None,
        "next_sentiment_run": sentiment_job.next_run_time.isoformat() if sentiment_job and sentiment_job.next_run_time else None,
    }


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
    configure_scheduler_jobs()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
