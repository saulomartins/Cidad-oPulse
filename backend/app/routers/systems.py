from __future__ import annotations

import json
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AwardOpportunity, Mention, MonitoredSystem
from app.schemas import SystemCreate, SystemOut, SystemUpdate

router = APIRouter(prefix="/api/systems", tags=["systems"])


def _slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", norm.lower()).strip("-")
    return slug or "sistema"


def _serialize_system(db: Session, sys_obj: MonitoredSystem) -> SystemOut:
    mentions_count, avg_sent = (
        db.query(func.count(Mention.id), func.avg(Mention.sentiment_score))
        .filter(Mention.system_id == sys_obj.id)
        .first()
    )
    awards_count = (
        db.query(func.count(AwardOpportunity.id))
        .filter(AwardOpportunity.system_id == sys_obj.id)
        .scalar()
        or 0
    )
    try:
        urls = json.loads(sys_obj.urls_json or "[]")
    except json.JSONDecodeError:
        urls = []
    try:
        keywords = json.loads(sys_obj.keywords_json or "[]")
    except json.JSONDecodeError:
        keywords = []
    try:
        social_profiles = json.loads(getattr(sys_obj, "social_profiles_json", "[]") or "[]")
    except json.JSONDecodeError:
        social_profiles = []

    return SystemOut(
        id=sys_obj.id,
        slug=sys_obj.slug,
        name=sys_obj.name,
        description=sys_obj.description,
        urls=urls,
        keywords=keywords,
        social_profiles=social_profiles,
        stage=sys_obj.stage,
        uses_ai=sys_obj.uses_ai,
        ai_details=sys_obj.ai_details,
        citizen_area=sys_obj.citizen_area,
        target_audience=sys_obj.target_audience,
        organization_type=sys_obj.organization_type,
        country=sys_obj.country,
        state_uf=sys_obj.state_uf,
        municipality=sys_obj.municipality,
        impact_summary=sys_obj.impact_summary,
        monitor_sentiment=sys_obj.monitor_sentiment,
        monitor_awards=sys_obj.monitor_awards,
        is_active=sys_obj.is_active,
        created_at=sys_obj.created_at,
        updated_at=sys_obj.updated_at,
        mentions_count=int(mentions_count or 0),
        avg_sentiment=round(float(avg_sent or 0.0), 2),
        awards_count=int(awards_count),
    )


@router.get("", response_model=list[SystemOut])
def list_systems(db: Session = Depends(get_db)):
    systems = db.query(MonitoredSystem).order_by(MonitoredSystem.created_at.desc()).all()
    return [_serialize_system(db, s) for s in systems]


@router.post("", response_model=SystemOut, status_code=201)
def create_system(payload: SystemCreate, db: Session = Depends(get_db)):
    base_slug = _slugify(payload.name)
    slug = base_slug
    counter = 2
    while db.query(MonitoredSystem).filter(MonitoredSystem.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    clean_urls = [u.strip() for u in payload.urls if u.strip()]
    clean_keywords = [k.strip() for k in payload.keywords if k.strip()]
    clean_profiles = [p.strip() for p in payload.social_profiles if p.strip()]

    obj = MonitoredSystem(
        name=payload.name.strip(),
        slug=slug,
        description=payload.description.strip(),
        urls_json=json.dumps(clean_urls, ensure_ascii=False),
        keywords_json=json.dumps(clean_keywords, ensure_ascii=False),
        social_profiles_json=json.dumps(clean_profiles, ensure_ascii=False),
        stage=payload.stage,
        uses_ai=payload.uses_ai,
        ai_details=payload.ai_details.strip(),
        citizen_area=payload.citizen_area.strip(),
        target_audience=payload.target_audience.strip(),
        organization_type=payload.organization_type.strip(),
        country=payload.country.strip(),
        state_uf=payload.state_uf.strip().upper() if len(payload.state_uf.strip()) == 2 else payload.state_uf.strip(),
        municipality=payload.municipality.strip(),
        impact_summary=payload.impact_summary.strip(),
        monitor_sentiment=payload.monitor_sentiment,
        monitor_awards=payload.monitor_awards,
        is_active=payload.is_active,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _serialize_system(db, obj)


@router.get("/{system_id}", response_model=SystemOut)
def get_system(system_id: int, db: Session = Depends(get_db)):
    obj = db.query(MonitoredSystem).filter(MonitoredSystem.id == system_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")
    return _serialize_system(db, obj)


@router.put("/{system_id}", response_model=SystemOut)
def update_system(system_id: int, payload: SystemUpdate, db: Session = Depends(get_db)):
    obj = db.query(MonitoredSystem).filter(MonitoredSystem.id == system_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    data = payload.model_dump(exclude_unset=True)
    if "urls" in data:
        obj.urls_json = json.dumps([u.strip() for u in data.pop("urls") if u.strip()], ensure_ascii=False)
    if "keywords" in data:
        obj.keywords_json = json.dumps([k.strip() for k in data.pop("keywords") if k.strip()], ensure_ascii=False)
    if "social_profiles" in data:
        obj.social_profiles_json = json.dumps([p.strip() for p in data.pop("social_profiles") if p.strip()], ensure_ascii=False)

    for key, value in data.items():
        if key == "state_uf" and isinstance(value, str):
            cleaned = value.strip()
            setattr(obj, key, cleaned.upper() if len(cleaned) == 2 else cleaned)
        else:
            setattr(obj, key, value.strip() if isinstance(value, str) else value)

    db.commit()
    db.refresh(obj)
    return _serialize_system(db, obj)


@router.delete("/{system_id}", status_code=204)
def delete_system(system_id: int, db: Session = Depends(get_db)):
    obj = db.query(MonitoredSystem).filter(MonitoredSystem.id == system_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")
    db.delete(obj)
    db.commit()
    return None
