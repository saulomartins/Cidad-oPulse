from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_runtime_config
from app.connectors import get_connector_registry
from app.connectors.base import CollectedMention
from app.models import JobRun, Mention, MonitoredSystem
from app.services.awards_radar import run_awards_radar_for_system
from app.services.notifier import send_notification
from app.services.relevance import evaluate_mention_quality, evaluate_mention_relevance, strip_html
from app.services.sentiment import analyze_mentions_batch

logger = logging.getLogger(__name__)


async def ingest_collected_mentions(
    db: Session,
    system: MonitoredSystem,
    collected: list[CollectedMention],
    runtime_config: dict[str, Any],
) -> tuple[int, int, list[str]]:
    """
    Deduplicate, relevance-filter (unless bypass_relevance is set on comments of a relevant post),
    run sentiment analysis, and persist collected mentions/comments.
    Returns (new_saved_count, filtered_out_count, crisis_highlights).
    """
    existing_hashes = {
        row[0]
        for row in db.query(Mention.content_hash)
        .filter(Mention.system_id == system.id)
        .all()
    }
    unique_new: list[CollectedMention] = []
    seen_local: set[str] = set()
    filtered_out = 0

    for item in collected:
        item.title = strip_html(item.title)
        item.content = strip_html(item.content)
        chash = item.content_hash()
        if chash in existing_hashes or chash in seen_local:
            continue
        seen_local.add(chash)

        ok_quality, quality_reason = evaluate_mention_quality(
            source_connector=item.source_connector,
            platform=item.platform,
            content_type=item.content_type or "mention",
            title=item.title,
            content=item.content,
            url=item.url,
            system=system,
        )
        if not ok_quality:
            filtered_out += 1
            logger.info(
                "Filtered low-trust/spam mention for %s: '%s' (%s)",
                system.name,
                item.title[:80],
                quality_reason,
            )
            continue

        if not item.bypass_relevance:
            is_rel, _rel_score, rel_reason = evaluate_mention_relevance(
                system,
                title=item.title,
                content=item.content,
                url=item.url,
                matched_keyword=item.matched_keyword,
            )
            if not is_rel:
                filtered_out += 1
                logger.info(
                    "Filtered irrelevant mention for %s: '%s' (%s)",
                    system.name,
                    item.title[:80],
                    rel_reason,
                )
                continue

        unique_new.append(item)

    if not unique_new:
        return 0, filtered_out, []

    analysis_inputs = [
        {
            "platform": m.platform,
            "content_type": m.content_type or "mention",
            "title": m.title,
            "content": m.content,
        }
        for m in unique_new
    ]
    analyzed = await analyze_mentions_batch(
        system.name, system.description, analysis_inputs, runtime_config
    )

    new_saved = 0
    crisis_highlights: list[str] = []

    for raw_mention, sent in zip(unique_new, analyzed):
        # Always honor AI semantic relevance filtering (including off-topic comments on gov posts!)
        if sent.get("is_relevant") is False:
            filtered_out += 1
            continue

        mention = Mention(
            system_id=system.id,
            content_hash=raw_mention.content_hash(),
            source_connector=raw_mention.source_connector,
            platform=raw_mention.platform,
            content_type=raw_mention.content_type or "mention",
            parent_post_url=raw_mention.parent_post_url or "",
            title=raw_mention.title,
            content=raw_mention.content,
            url=raw_mention.url,
            author=raw_mention.author,
            matched_keyword=raw_mention.matched_keyword,
            published_at=raw_mention.published_at,
            sentiment=sent["sentiment"],
            sentiment_score=sent["sentiment_score"],
            confidence=sent["confidence"],
            topics_json=json.dumps(sent["topics"], ensure_ascii=False),
            summary=sent["summary"],
            sentiment_reason=sent.get("sentiment_reason", ""),
            evidence_quote=sent.get("evidence_quote", ""),
            is_crisis_signal=sent["is_crisis_signal"],
            analyzed_by=sent["analyzed_by"],
        )
        db.add(mention)
        new_saved += 1

        if sent["is_crisis_signal"]:
            crisis_highlights.append(
                f"[{system.name} | {raw_mention.platform}] {sent['summary']} ({raw_mention.url})"
            )

    db.commit()
    return new_saved, filtered_out, crisis_highlights


async def run_sentiment_scan(
    db: Session,
    system_id: int | None = None,
    connector_ids: list[str] | None = None,
    lookback_days: int = 365,
    trigger: str = "manual",
) -> JobRun:
    """Run sentiment collection and analysis for one or all active systems."""
    job = JobRun(
        job_type="sentiment_scan",
        trigger=trigger,
        system_id=system_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        runtime_config = get_runtime_config(db)
        registry = get_connector_registry()

        if connector_ids:
            selected_connectors = [registry[cid] for cid in connector_ids if cid in registry]
        else:
            selected_connectors = [c for c in registry.values() if c.is_configured(runtime_config)]

        query = db.query(MonitoredSystem).filter(MonitoredSystem.is_active == True)  # noqa: E712
        if system_id is not None:
            query = query.filter(MonitoredSystem.id == system_id)
        else:
            query = query.filter(MonitoredSystem.monitor_sentiment == True)  # noqa: E712
        systems = query.all()

        total_found = 0
        total_filtered_out = 0
        total_new = 0
        crisis_highlights: list[str] = []

        for system in systems:
            tasks = [
                connector.collect(system, runtime_config, max_results=12, lookback_days=lookback_days)
                for connector in selected_connectors
                if connector.is_configured(runtime_config)
            ]
            raw_batches = await asyncio.gather(*tasks, return_exceptions=True)

            collected: list[CollectedMention] = []
            for batch in raw_batches:
                if isinstance(batch, list):
                    collected.extend(batch)
                elif isinstance(batch, Exception):
                    logger.warning("Connector error during sentiment scan: %s", batch)

            total_found += len(collected)
            saved, filtered, crises = await ingest_collected_mentions(
                db, system, collected, runtime_config
            )
            total_new += saved
            total_filtered_out += filtered
            crisis_highlights.extend(crises)

        used_names = [c.name for c in selected_connectors if c.is_configured(runtime_config)]
        job.status = "completed"
        job.items_found = total_found
        job.new_items = total_new
        filtered_note = f", {total_filtered_out} descartada(s) por baixa relevância" if total_filtered_out else ""
        job.summary = (
            f"Varredura concluída em {len(systems)} sistema(s) usando {', '.join(used_names) or 'nenhum conector ativo'}. "
            f"{total_found} coletadas{filtered_note}, {total_new} nova(s) relevante(s) salva(s)"
            + (f" ({len(crisis_highlights)} sinal(is) de crise)." if crisis_highlights else ".")
        )
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        if crisis_highlights:
            await send_notification(
                db,
                runtime_config,
                title=f"Alerta de Sentimento Crítico ({len(crisis_highlights)} sinal/sinais)",
                markdown_body=job.summary,
                highlights=crisis_highlights,
            )

        return job

    except Exception as exc:
        logger.exception("Sentiment scan failed")
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job


async def run_awards_radar_job(
    db: Session,
    system_id: int | None = None,
    focus_scope: str = "todos",
    include_ai_filter: str = "auto",
    trigger: str = "manual",
) -> JobRun:
    """Execute global awards & contests radar for one or all active systems."""
    job = JobRun(
        job_type="awards_radar",
        trigger=trigger,
        system_id=system_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        runtime_config = get_runtime_config(db)
        query = db.query(MonitoredSystem).filter(MonitoredSystem.is_active == True)  # noqa: E712
        if system_id is not None:
            query = query.filter(MonitoredSystem.id == system_id)
        else:
            query = query.filter(MonitoredSystem.monitor_awards == True)  # noqa: E712
        systems = query.all()

        total_evaluated = 0
        total_new = 0
        highlights: list[str] = []

        for system in systems:
            evaluated, new_cnt, top_new = await run_awards_radar_for_system(
                db,
                system,
                runtime_config,
                focus_scope=focus_scope,
                include_ai_filter=include_ai_filter,
            )
            total_evaluated += evaluated
            total_new += new_cnt
            for award in top_new[:3]:
                url_suffix = f" — {award.official_url}" if award.official_url else ""
                highlights.append(
                    f"[{system.name}] {award.title} ({award.country_region}) — Match {award.match_score}% | Prazo: {award.deadline}{url_suffix}"
                )

        mode_label = (
            f"Gemini ({runtime_config.get('gemini_model', 'gemini-4-hydrogen')}) + Google Search Global + Catálogo Curado"
            if runtime_config.get("gemini_api_key")
            else "Catálogo Global Curado (configure GEMINI_API_KEY para busca ao vivo na web mundial)"
        )
        job.status = "completed"
        job.items_found = total_evaluated
        job.new_items = total_new
        job.summary = (
            f"Radar mundial executado para {len(systems)} sistema(s) [{mode_label}]. "
            f"{total_evaluated} premiações avaliadas, {total_new} nova(s) oportunidade(s) registrada(s)."
        )
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        # Notify on scheduled weekly runs or when new high-match awards are discovered
        if trigger == "scheduled" or (total_new > 0 and highlights):
            await send_notification(
                db,
                runtime_config,
                title=f"Radar Semanal de Prêmios — {total_new} nova(s) oportunidade(s)",
                markdown_body=job.summary,
                highlights=highlights,
            )

        return job

    except Exception as exc:
        logger.exception("Awards radar job failed")
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job
