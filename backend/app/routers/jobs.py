from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobRun
from app.schemas import JobRunOut
from app.services.scheduler import get_next_run_times

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRunOut])
def list_job_runs(
    job_type: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(JobRun)
    if job_type:
        q = q.filter(JobRun.job_type == job_type)
    return q.order_by(JobRun.started_at.desc()).limit(limit).all()


@router.get("/schedule")
def get_schedule_status():
    return get_next_run_times()
