from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config import get_runtime_config
from app.database import get_db
from app.models import AwardOpportunity, MonitoredSystem
from app.schemas import AwardOut, AwardPipelineUpdate, AwardsScanRequest, JobRunOut
from app.services.awards_radar import (
    enrich_existing_awards_metadata,
    is_award_open_with_buffer,
    resolve_award_geolocation,
    verify_awards_deadlines_live,
)
from app.services.monitor_runner import run_awards_radar_job

router = APIRouter(prefix="/api/awards", tags=["awards"])


def _serialize_award(
    a: AwardOpportunity,
    system_map: dict[int, str],
    min_days_ahead: int = 15,
    include_upcoming_cycles: bool = False,
) -> AwardOut:
    try:
        categories = json.loads(a.categories_json or "[]")
    except json.JSONDecodeError:
        categories = []
    country, city, lat, lng = resolve_award_geolocation(
        country=getattr(a, "country", "") or "",
        city=getattr(a, "city", "") or "",
        country_region=a.country_region,
        latitude=getattr(a, "latitude", None),
        longitude=getattr(a, "longitude", None),
    )
    deadline_date = getattr(a, "deadline_date", "") or ""
    is_open, days_rem = is_award_open_with_buffer(
        a.award_status,
        deadline_date,
        min_days_ahead=min_days_ahead,
        include_upcoming_cycles=include_upcoming_cycles,
    )
    return AwardOut(
        id=a.id,
        system_id=a.system_id,
        system_name=system_map.get(a.system_id, ""),
        title=a.title,
        organizer=a.organizer,
        description=a.description,
        official_url=a.official_url,
        scope=a.scope,
        country_region=a.country_region,
        country=country,
        city=city,
        latitude=lat,
        longitude=lng,
        ai_requirement=a.ai_requirement,
        stage_eligibility=a.stage_eligibility,
        deadline=a.deadline,
        deadline_date=deadline_date,
        days_remaining=days_rem,
        is_open_for_application=is_open,
        award_status=a.award_status,
        deadline_verified_at=getattr(a, "deadline_verified_at", None),
        deadline_source_note=getattr(a, "deadline_source_note", "") or "",
        prize_benefits=a.prize_benefits,
        categories=categories,
        match_score=a.match_score,
        match_reasoning=a.match_reasoning,
        next_steps=a.next_steps,
        discovery_source=a.discovery_source,
        pipeline_status=a.pipeline_status,
        user_notes=a.user_notes,
        discovered_at=a.discovered_at,
        updated_at=a.updated_at,
    )


@router.get("", response_model=list[AwardOut])
def list_awards(
    system_id: int | None = Query(default=None),
    scope: str | None = Query(default=None),
    ai_requirement: str | None = Query(default=None),
    stage_eligibility: str | None = Query(default=None),
    pipeline_status: str | None = Query(default=None),
    min_match: int = Query(default=0, ge=0, le=100),
    min_days_ahead: int = Query(default=15, ge=0, le=365),
    include_upcoming_cycles: bool = Query(default=False),
    include_expired: bool = Query(default=False),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    enrich_existing_awards_metadata(db)

    q = db.query(AwardOpportunity)
    if system_id is not None:
        q = q.filter(AwardOpportunity.system_id == system_id)
    if scope:
        q = q.filter(AwardOpportunity.scope == scope)
    if ai_requirement:
        q = q.filter(AwardOpportunity.ai_requirement == ai_requirement)
    if stage_eligibility:
        q = q.filter(AwardOpportunity.stage_eligibility == stage_eligibility)
    if pipeline_status:
        q = q.filter(AwardOpportunity.pipeline_status == pipeline_status)
    if min_match > 0:
        q = q.filter(AwardOpportunity.match_score >= min_match)

    rows = q.order_by(AwardOpportunity.match_score.desc(), AwardOpportunity.discovered_at.desc()).all()
    if search:
        s_lower = search.lower()
        rows = [
            r for r in rows
            if s_lower in r.title.lower()
            or s_lower in r.organizer.lower()
            or s_lower in r.description.lower()
            or s_lower in r.country_region.lower()
            or s_lower in (getattr(r, "country", "") or "").lower()
            or s_lower in (getattr(r, "city", "") or "").lower()
        ]

    system_map = {s.id: s.name for s in db.query(MonitoredSystem.id, MonitoredSystem.name).all()}
    serialized = [
        _serialize_award(
            r,
            system_map,
            min_days_ahead=min_days_ahead,
            include_upcoming_cycles=include_upcoming_cycles,
        )
        for r in rows
    ]
    if not include_expired:
        serialized = [a for a in serialized if a.is_open_for_application]
    return serialized


@router.post("/verify-deadlines")
async def verify_deadlines_live(
    system_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    runtime_config = get_runtime_config(db)
    return await verify_awards_deadlines_live(db, runtime_config, system_id=system_id)


@router.post("/scan", response_model=JobRunOut)
async def trigger_awards_scan(payload: AwardsScanRequest, db: Session = Depends(get_db)):
    job = await run_awards_radar_job(
        db,
        system_id=payload.system_id,
        focus_scope=payload.focus_scope,
        include_ai_filter=payload.include_ai_filter,
        trigger="manual",
    )
    return job


@router.patch("/{award_id}", response_model=AwardOut)
def update_award_pipeline(award_id: int, payload: AwardPipelineUpdate, db: Session = Depends(get_db)):
    obj = db.query(AwardOpportunity).filter(AwardOpportunity.id == award_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Premiação não encontrada")

    if payload.pipeline_status is not None:
        obj.pipeline_status = payload.pipeline_status
    if payload.user_notes is not None:
        obj.user_notes = payload.user_notes
    if payload.award_status is not None:
        obj.award_status = payload.award_status
    if payload.deadline is not None:
        obj.deadline = payload.deadline
    if payload.deadline_date is not None:
        obj.deadline_date = payload.deadline_date
    if payload.deadline_source_note is not None:
        obj.deadline_source_note = payload.deadline_source_note

    db.commit()
    db.refresh(obj)
    system_map = {s.id: s.name for s in db.query(MonitoredSystem.id, MonitoredSystem.name).all()}
    return _serialize_award(obj, system_map)


@router.delete("/{award_id}", status_code=204)
def delete_award(award_id: int, db: Session = Depends(get_db)):
    obj = db.query(AwardOpportunity).filter(AwardOpportunity.id == award_id).first()
    if obj:
        db.delete(obj)
        db.commit()
    return None


@router.get("/export/report")
def export_awards_report(
    format: str = Query(default="markdown", pattern="^(markdown|csv)$"),
    system_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(AwardOpportunity)
    if system_id is not None:
        q = q.filter(AwardOpportunity.system_id == system_id)
    awards = q.order_by(AwardOpportunity.match_score.desc()).all()
    system_map = {s.id: s.name for s in db.query(MonitoredSystem.id, MonitoredSystem.name).all()}

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Sistema", "Prêmio/Concurso", "Organizador", "Abrangência", "País/Região",
            "Requisito IA", "Estágio Elegível", "Match (%)", "Prazo", "Status", "Pipeline", "URL Oficial"
        ])
        for a in awards:
            writer.writerow([
                system_map.get(a.system_id, ""),
                a.title,
                a.organizer,
                a.scope,
                a.country_region,
                a.ai_requirement,
                a.stage_eligibility,
                a.match_score,
                a.deadline,
                a.award_status,
                a.pipeline_status,
                a.official_url,
            ])
        return PlainTextResponse(
            content=buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=radar_premiacoes.csv"},
        )

    lines = [
        f"# Relatório Semanal — Radar Mundial de Premiações ({datetime.now().strftime('%d/%m/%Y')})",
        "",
        f"Total de oportunidades mapeadas: **{len(awards)}**",
        "",
    ]
    for a in awards:
        lines.extend([
            f"## {a.title} ({a.match_score}% de aderência)",
            f"- **Sistema indicado:** {system_map.get(a.system_id, '')}",
            f"- **Organizador:** {a.organizer} ({a.country_region} — {a.scope})",
            f"- **IA:** `{a.ai_requirement}` | **Estágio:** `{a.stage_eligibility}` | **Status:** `{a.award_status}`",
            f"- **Prazo:** {a.deadline}",
            f"- **Benefícios:** {a.prize_benefits}",
            f"- **Por que combina:** {a.match_reasoning}",
            f"- **Próximos passos:** {a.next_steps}",
            f"- **Link oficial:** {a.official_url}",
            "",
        ])

    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=radar_premiacoes.md"},
    )
