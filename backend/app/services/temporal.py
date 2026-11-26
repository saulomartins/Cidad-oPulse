from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Mention, MonitoredSystem


SOCIAL_PLATFORMS = {"x", "instagram", "facebook", "linkedin", "youtube", "tiktok", "reddit"}
STANDARD_WINDOWS: list[tuple[int, str]] = [
    (7, "7 dias"),
    (14, "14 dias"),
    (30, "30 dias"),
    (180, "6 meses"),
    (365, "1 ano"),
]

MONTH_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def mention_timestamp(m: Mention) -> datetime:
    dt = as_utc(m.published_at) or as_utc(m.collected_at)
    return dt or datetime.now(timezone.utc)


def _summarize_window(days: int, label: str, items: list[Mention]) -> dict[str, Any]:
    total = len(items)
    pos = sum(1 for m in items if m.sentiment == "positivo")
    neu = sum(1 for m in items if m.sentiment == "neutro")
    neg = sum(1 for m in items if m.sentiment == "negativo")
    crisis = sum(1 for m in items if m.is_crisis_signal)
    avg_score = round(sum(m.sentiment_score for m in items) / total, 2) if total else 0.0
    sentiment_index = int(round(((avg_score + 1.0) / 2.0) * 100)) if total else 50
    return {
        "days": days,
        "label": label,
        "total_mentions": total,
        "positive_count": pos,
        "neutral_count": neu,
        "negative_count": neg,
        "crisis_count": crisis,
        "avg_score": avg_score,
        "sentiment_index": sentiment_index,
        "positive_pct": round((pos / total) * 100, 1) if total else 0.0,
        "neutral_pct": round((neu / total) * 100, 1) if total else 0.0,
        "negative_pct": round((neg / total) * 100, 1) if total else 0.0,
    }


def _period_label(days: int) -> str:
    for d, lbl in STANDARD_WINDOWS:
        if d == days:
            return lbl
    return f"{days} dias"


def _month_shift(year: int, month: int, delta_months: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + delta_months
    return total // 12, (total % 12) + 1


def _build_continuous_series(
    items: list[Mention],
    days: int,
    now: datetime,
) -> tuple[str, list[dict[str, Any]]]:
    """Generate continuous time buckets with zero gaps (daily for <= 30d, monthly for 6m/1y)."""
    if days <= 30:
        granularity = "day"
        buckets: dict[str, dict[str, Any]] = {}
        start_day = (now - timedelta(days=days - 1)).date()
        ordered_keys: list[str] = []
        for i in range(days):
            d = start_day + timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            ordered_keys.append(key)
            buckets[key] = {
                "bucket": key,
                "label": d.strftime("%d/%m"),
                "positivo": 0,
                "neutro": 0,
                "negativo": 0,
                "scores": [],
            }
        for m in items:
            key = mention_timestamp(m).date().strftime("%Y-%m-%d")
            if key in buckets:
                buckets[key][m.sentiment] += 1
                buckets[key]["scores"].append(m.sentiment_score)
    else:
        granularity = "month"
        num_months = 6 if days <= 185 else 12
        buckets = {}
        ordered_keys = []
        for offset in range(-(num_months - 1), 1):
            yr, mo = _month_shift(now.year, now.month, offset)
            key = f"{yr:04d}-{mo:02d}"
            ordered_keys.append(key)
            buckets[key] = {
                "bucket": key,
                "label": f"{MONTH_PT[mo]}/{str(yr)[2:]}",
                "positivo": 0,
                "neutro": 0,
                "negativo": 0,
                "scores": [],
            }
        for m in items:
            dt = mention_timestamp(m)
            key = f"{dt.year:04d}-{dt.month:02d}"
            if key in buckets:
                buckets[key][m.sentiment] += 1
                buckets[key]["scores"].append(m.sentiment_score)

    series: list[dict[str, Any]] = []
    for key in ordered_keys:
        b = buckets[key]
        scores = b["scores"]
        total = b["positivo"] + b["neutro"] + b["negativo"]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        sent_idx = int(round(((avg_score + 1.0) / 2.0) * 100)) if scores else None
        series.append(
            {
                "bucket": b["bucket"],
                "label": b["label"],
                "positivo": b["positivo"],
                "neutro": b["neutro"],
                "negativo": b["negativo"],
                "total": total,
                "avg_score": avg_score,
                "sentiment_index": sent_idx,
            }
        )

    return granularity, series


def _build_channel_groups(items: list[Mention]) -> list[dict[str, Any]]:
    groups_def = [
        ("redes_sociais", "Redes Sociais", lambda p: p in SOCIAL_PLATFORMS),
        ("internet", "Internet, Portais & Notícias", lambda p: p not in SOCIAL_PLATFORMS),
    ]
    out: list[dict[str, Any]] = []
    for gid, label, pred in groups_def:
        subset = [m for m in items if pred((m.platform or "web").lower())]
        total = len(subset)
        pos = sum(1 for m in subset if m.sentiment == "positivo")
        neu = sum(1 for m in subset if m.sentiment == "neutro")
        neg = sum(1 for m in subset if m.sentiment == "negativo")
        avg_s = sum(m.sentiment_score for m in subset) / total if total else 0.0
        sent_idx = int(round(((avg_s + 1.0) / 2.0) * 100)) if total else 50
        plat_counts = Counter((m.platform or "web").lower() for m in subset)
        out.append(
            {
                "group": gid,
                "label": label,
                "total_mentions": total,
                "positive_count": pos,
                "neutral_count": neu,
                "negative_count": neg,
                "sentiment_index": sent_idx,
                "platforms": [{"platform": p, "count": c} for p, c in plat_counts.most_common()],
            }
        )
    return out


def build_temporal_analysis(
    db: Session,
    system_id: int | None = None,
    days: int = 30,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    days = max(1, min(730, int(days)))

    system_name = "Todos os sistemas"
    q = db.query(Mention)
    if system_id is not None:
        q = q.filter(Mention.system_id == system_id)
        sys_obj = db.query(MonitoredSystem).filter(MonitoredSystem.id == system_id).first()
        if sys_obj:
            system_name = sys_obj.name

    all_mentions = q.all()

    # Pre-compute timestamps once
    dated: list[tuple[datetime, Mention]] = [(mention_timestamp(m), m) for m in all_mentions]

    cutoff_current = now - timedelta(days=days)
    cutoff_previous = now - timedelta(days=days * 2)

    current_items = [m for dt, m in dated if dt >= cutoff_current]
    previous_items = [m for dt, m in dated if cutoff_previous <= dt < cutoff_current]

    period_lbl = _period_label(days)
    current_summary = _summarize_window(days, period_lbl, current_items)
    previous_summary = _summarize_window(days, f"Período anterior ({period_lbl})", previous_items)

    mentions_delta = current_summary["total_mentions"] - previous_summary["total_mentions"]
    sentiment_index_delta = (
        current_summary["sentiment_index"] - previous_summary["sentiment_index"]
        if previous_summary["total_mentions"] > 0 and current_summary["total_mentions"] > 0
        else 0
    )

    if current_summary["total_mentions"] == 0:
        trend_direction = "sem_dados"
    elif previous_summary["total_mentions"] == 0:
        trend_direction = "melhorando" if current_summary["sentiment_index"] >= 60 else (
            "piorando" if current_summary["sentiment_index"] <= 40 else "estavel"
        )
    elif sentiment_index_delta >= 4:
        trend_direction = "melhorando"
    elif sentiment_index_delta <= -4:
        trend_direction = "piorando"
    else:
        trend_direction = "estavel"

    # Multi-window simultaneous summary (7d, 14d, 30d, 6m, 1y)
    windows_summary = []
    for win_days, win_lbl in STANDARD_WINDOWS:
        win_cutoff = now - timedelta(days=win_days)
        win_items = [m for dt, m in dated if dt >= win_cutoff]
        windows_summary.append(_summarize_window(win_days, win_lbl, win_items))

    granularity, series = _build_continuous_series(current_items, days, now)
    channel_groups = _build_channel_groups(current_items)

    topic_counter: Counter[str] = Counter()
    for m in current_items:
        try:
            for t in json.loads(m.topics_json or "[]"):
                topic_counter[str(t)] += 1
        except json.JSONDecodeError:
            pass
    top_topics = [{"topic": k, "count": v} for k, v in topic_counter.most_common(8)]

    # Narrative executive summary in PT-BR
    if current_summary["total_mentions"] == 0:
        narrative = (
            f"Nenhuma menção encontrada para {system_name} nos últimos {period_lbl}. "
            f"Use o botão 'Coletar período selecionado' para pesquisar dados históricos nesta janela."
        )
    else:
        social_cnt = channel_groups[0]["total_mentions"]
        web_cnt = channel_groups[1]["total_mentions"]
        tone = (
            "percepção predominantemente positiva"
            if current_summary["sentiment_index"] >= 65
            else "percepção predominantemente negativa"
            if current_summary["sentiment_index"] <= 40
            else "percepção equilibrada/neutra"
        )
        delta_txt = ""
        if previous_summary["total_mentions"] > 0:
            sign = "+" if sentiment_index_delta > 0 else ""
            delta_txt = f" ({sign}{sentiment_index_delta} pts em relação aos {period_lbl} anteriores)."
        else:
            delta_txt = "."
        crisis_txt = (
            f" Atenção: {current_summary['crisis_count']} sinal(is) de crise detectado(s)."
            if current_summary["crisis_count"] > 0
            else ""
        )
        narrative = (
            f"Nos últimos {period_lbl}, {system_name} registrou {current_summary['total_mentions']} menções "
            f"({social_cnt} em redes sociais e {web_cnt} na internet/notícias), com Índice de Sentimento "
            f"{current_summary['sentiment_index']}/100 — {tone}{delta_txt}{crisis_txt}"
        )

    return {
        "system_id": system_id,
        "system_name": system_name,
        "period_days": days,
        "period_label": period_lbl,
        "granularity": granularity,
        "date_from": cutoff_current.date().isoformat(),
        "date_to": now.date().isoformat(),
        "current": current_summary,
        "previous": previous_summary,
        "mentions_delta": mentions_delta,
        "sentiment_index_delta": sentiment_index_delta,
        "trend_direction": trend_direction,
        "narrative_summary": narrative,
        "windows_summary": windows_summary,
        "series": series,
        "channel_groups": channel_groups,
        "top_topics": top_topics,
    }
