from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_runtime_config
from app.connectors.base import CollectedMention
from app.connectors.social_paid import ApifySocialConnector
from app.database import get_db
from app.models import Mention, MonitoredSystem
from app.schemas import (
    FetchPostCommentsRequest,
    ImportCommentsRequest,
    JobRunOut,
    MentionOut,
    ProblemDiagnosticsOut,
    ScanRequest,
    SentimentOverview,
    SentimentTrendPoint,
    TemporalAnalysisOut,
)
from app.services.monitor_runner import ingest_collected_mentions, run_sentiment_scan
from app.services.problem_analytics import build_problem_diagnostics
from app.services.relevance import evaluate_mention_quality, evaluate_mention_relevance, strip_html
from app.services.temporal import build_temporal_analysis, mention_timestamp

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


def _serialize_mention(m: Mention, system_map: dict[int, str]) -> MentionOut:
    try:
        topics = json.loads(m.topics_json or "[]")
    except json.JSONDecodeError:
        topics = []
    return MentionOut(
        id=m.id,
        system_id=m.system_id,
        system_name=system_map.get(m.system_id, ""),
        source_connector=m.source_connector,
        platform=m.platform,
        content_type=getattr(m, "content_type", "mention") or "mention",
        parent_post_url=getattr(m, "parent_post_url", "") or "",
        title=m.title,
        content=m.content,
        url=m.url,
        author=m.author,
        matched_keyword=m.matched_keyword,
        published_at=m.published_at,
        sentiment=m.sentiment,
        sentiment_score=m.sentiment_score,
        confidence=m.confidence,
        topics=topics,
        summary=m.summary,
        sentiment_reason=getattr(m, "sentiment_reason", "") or "",
        evidence_quote=getattr(m, "evidence_quote", "") or "",
        is_crisis_signal=m.is_crisis_signal,
        analyzed_by=m.analyzed_by,
        collected_at=m.collected_at,
    )


@router.get("/overview", response_model=SentimentOverview)
def get_sentiment_overview(
    system_id: int | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=730),
    db: Session = Depends(get_db),
):
    q = db.query(Mention)
    if system_id is not None:
        q = q.filter(Mention.system_id == system_id)
    mentions = q.order_by(Mention.collected_at.asc()).all()
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        mentions = [m for m in mentions if mention_timestamp(m) >= cutoff]

    total = len(mentions)
    pos = sum(1 for m in mentions if m.sentiment == "positivo")
    neu = sum(1 for m in mentions if m.sentiment == "neutro")
    neg = sum(1 for m in mentions if m.sentiment == "negativo")
    crisis = sum(1 for m in mentions if m.is_crisis_signal)
    avg_score = round(sum(m.sentiment_score for m in mentions) / total, 2) if total else 0.0
    sentiment_index = int(round(((avg_score + 1.0) / 2.0) * 100)) if total else 50

    platform_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    by_day: dict[str, dict] = defaultdict(lambda: {"positivo": 0, "neutro": 0, "negativo": 0, "scores": []})

    for m in mentions:
        platform_counter[m.platform] += 1
        try:
            for t in json.loads(m.topics_json or "[]"):
                topic_counter[str(t)] += 1
        except json.JSONDecodeError:
            pass
        dt = m.published_at or m.collected_at
        day_key = dt.strftime("%Y-%m-%d") if dt else "N/A"
        by_day[day_key][m.sentiment] += 1
        by_day[day_key]["scores"].append(m.sentiment_score)

    trend = [
        SentimentTrendPoint(
            date=day,
            positivo=vals["positivo"],
            neutro=vals["neutro"],
            negativo=vals["negativo"],
            avg_score=round(sum(vals["scores"]) / len(vals["scores"]), 2),
        )
        for day, vals in sorted(by_day.items())[-14:]
    ]

    return SentimentOverview(
        total_mentions=total,
        positive_count=pos,
        neutral_count=neu,
        negative_count=neg,
        crisis_count=crisis,
        avg_score=avg_score,
        sentiment_index=sentiment_index,
        by_platform=[{"platform": k, "count": v} for k, v in platform_counter.most_common(10)],
        top_topics=[{"topic": k, "count": v} for k, v in topic_counter.most_common(10)],
        trend=trend,
    )


@router.get("/temporal", response_model=TemporalAnalysisOut)
def get_temporal_analysis(
    system_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=730),
    db: Session = Depends(get_db),
):
    return build_temporal_analysis(db, system_id=system_id, days=days)


@router.get("/mentions", response_model=list[MentionOut])
def list_mentions(
    system_id: int | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=730),
    crisis_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Mention)
    if system_id is not None:
        q = q.filter(Mention.system_id == system_id)
    if sentiment:
        q = q.filter(Mention.sentiment == sentiment)
    if platform:
        q = q.filter(Mention.platform == platform)
    if crisis_only:
        q = q.filter(Mention.is_crisis_signal == True)  # noqa: E712

    rows = q.order_by(Mention.collected_at.desc()).limit(limit * 2 if days else limit).all()
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = [r for r in rows if mention_timestamp(r) >= cutoff]
    rows.sort(key=mention_timestamp, reverse=True)
    rows = rows[:limit]
    if search:
        s_lower = search.lower()
        rows = [
            r for r in rows
            if s_lower in r.title.lower()
            or s_lower in r.content.lower()
            or s_lower in r.summary.lower()
            or s_lower in r.author.lower()
        ]

    system_map = {s.id: s.name for s in db.query(MonitoredSystem.id, MonitoredSystem.name).all()}
    return [_serialize_mention(r, system_map) for r in rows]


@router.post("/scan", response_model=JobRunOut)
async def trigger_sentiment_scan(payload: ScanRequest, db: Session = Depends(get_db)):
    job = await run_sentiment_scan(
        db,
        system_id=payload.system_id,
        connector_ids=payload.connectors,
        lookback_days=payload.lookback_days or 365,
        trigger="manual",
    )
    return job


@router.post("/cleanup-irrelevant")
def cleanup_irrelevant_mentions(
    system_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Re-evaluate saved mentions using the relevance filter and remove false positives."""
    q = db.query(Mention)
    if system_id is not None:
        q = q.filter(Mention.system_id == system_id)
    mentions = q.all()
    systems_by_id = {s.id: s for s in db.query(MonitoredSystem).all()}

    removed = 0
    cleaned_html = 0
    for m in mentions:
        if m.source_connector == "seed":
            continue
        sys_obj = systems_by_id.get(m.system_id)
        if not sys_obj:
            continue

        new_title = strip_html(m.title)
        new_content = strip_html(m.content)
        if new_title != m.title or new_content != m.content:
            m.title = new_title
            m.content = new_content
            cleaned_html += 1

        ok_quality, _ = evaluate_mention_quality(
            source_connector=m.source_connector,
            platform=m.platform,
            content_type=m.content_type or "mention",
            title=m.title,
            content=m.content,
            url=m.url,
            system=sys_obj,
        )
        if not ok_quality:
            db.delete(m)
            removed += 1
            continue

        # Direct comments extracted from an already-relevant post (via Apify/Meta/YouTube)
        # do not need to repeat the system name inside every short reply.
        if m.content_type == "comment" and m.source_connector in {"apify_social", "meta_api", "youtube", "manual_import"}:
            continue

        is_rel, _, _ = evaluate_mention_relevance(
            sys_obj,
            title=m.title,
            content=m.content,
            url=m.url,
            matched_keyword=m.matched_keyword,
        )
        if not is_rel:
            db.delete(m)
            removed += 1

    db.commit()
    return {
        "evaluated": len(mentions),
        "removed": removed,
        "cleaned_html": cleaned_html,
    }


@router.get("/problems", response_model=ProblemDiagnosticsOut)
async def get_problem_diagnostics(
    system_id: int | None = Query(default=None),
    days: int | None = Query(default=365, ge=1, le=730),
    channel_group: str = Query(default="all", pattern="^(all|instagram_facebook|redes_sociais|internet)$"),
    use_ai: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return await build_problem_diagnostics(
        db, system_id=system_id, days=days, channel_group=channel_group, use_ai=use_ai
    )


def _parse_comment_lines(raw_text: str) -> list[tuple[str, str]]:
    """Parse comments from 'Author | Comment', CSV (author,comment), or plain one-per-line text."""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return []

    # Check if looks like CSV with header
    first_low = lines[0].lower()
    if ("," in lines[0] or ";" in lines[0]) and any(
        h in first_low for h in ("comment", "coment", "texto", "message", "mensagem", "text")
    ):
        delimiter = ";" if lines[0].count(";") > lines[0].count(",") else ","
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        parsed: list[tuple[str, str]] = []
        for row in reader:
            norm_row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            text = (
                norm_row.get("comment")
                or norm_row.get("comentario")
                or norm_row.get("comentário")
                or norm_row.get("text")
                or norm_row.get("texto")
                or norm_row.get("message")
                or norm_row.get("mensagem")
                or ""
            )
            author = (
                norm_row.get("author")
                or norm_row.get("autor")
                or norm_row.get("username")
                or norm_row.get("usuario")
                or norm_row.get("usuário")
                or "Usuário"
            )
            if text:
                parsed.append((author, text))
        if parsed:
            return parsed

    result: list[tuple[str, str]] = []
    for ln in lines:
        if "|" in ln:
            parts = ln.split("|", 1)
            author = parts[0].strip() or "Usuário"
            text = parts[1].strip()
        elif ":" in ln and len(ln.split(":", 1)[0]) <= 32 and ln.split(":", 1)[0].startswith("@"):
            parts = ln.split(":", 1)
            author = parts[0].strip()
            text = parts[1].strip()
        else:
            author = "Cidadão / Usuário"
            text = ln
        if len(text) >= 3:
            result.append((author, text))
    return result


@router.post("/import-comments")
async def import_social_comments(payload: ImportCommentsRequest, db: Session = Depends(get_db)):
    """Import comments pasted or exported from Instagram/Facebook/other networks and analyze sentiment & pain points."""
    system = db.query(MonitoredSystem).filter(MonitoredSystem.id == payload.system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    entries = _parse_comment_lines(payload.raw_text)
    if not entries:
        raise HTTPException(status_code=400, detail="Nenhum comentário válido encontrado no texto enviado.")

    now = datetime.now(timezone.utc)
    post_url = payload.post_url.strip()
    collected = [
        CollectedMention(
            source_connector="manual_import",
            platform=payload.platform,
            content_type="comment",
            parent_post_url=post_url,
            title=f"Comentário de {author} ({payload.platform.upper()})",
            content=text[:2000],
            url=post_url,
            author=author[:180],
            matched_keyword=f"Comentário {payload.platform}",
            published_at=now,
            bypass_relevance=True,
        )
        for author, text in entries[:150]
    ]

    runtime_config = get_runtime_config(db)
    saved, _filtered, crises = await ingest_collected_mentions(db, system, collected, runtime_config)
    return {
        "parsed": len(entries),
        "saved": saved,
        "duplicates_skipped": max(0, len(collected) - saved),
        "crisis_signals": len(crises),
    }


@router.post("/fetch-post-comments")
async def fetch_post_comments(payload: FetchPostCommentsRequest, db: Session = Depends(get_db)):
    """Extract public comments directly from an Instagram or Facebook post URL using Apify."""
    system = db.query(MonitoredSystem).filter(MonitoredSystem.id == payload.system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    runtime_config = get_runtime_config(db)
    if not runtime_config.get("apify_token"):
        raise HTTPException(
            status_code=400,
            detail="Configure o APIFY_TOKEN em Conectores & Alertas para extrair comentários automaticamente por URL do Instagram/Facebook (ou use a aba 'Importar Texto / CSV').",
        )

    apify = ApifySocialConnector()
    collected = await apify.collect_comments_from_post_url(
        payload.post_url.strip(), system, runtime_config, max_comments=payload.max_comments
    )
    saved, _filtered, crises = await ingest_collected_mentions(db, system, collected, runtime_config)
    return {
        "extracted": len(collected),
        "saved": saved,
        "crisis_signals": len(crises),
    }


@router.delete("/mentions/{mention_id}", status_code=204)
def delete_mention(mention_id: int, db: Session = Depends(get_db)):
    obj = db.query(Mention).filter(Mention.id == mention_id).first()
    if obj:
        db.delete(obj)
        db.commit()
    return None
