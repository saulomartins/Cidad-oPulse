from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_runtime_config
from app.models import Mention, MonitoredSystem
from app.services.gemini_client import call_gemini_interaction, extract_json_payload
from app.services.temporal import mention_timestamp

logger = logging.getLogger(__name__)

# In-memory cache keyed by (system_id, total_mentions, latest_mention_id, days, use_ai)
_STAR_RATING_CACHE: dict[tuple[int, int, int, int | None, bool], dict[str, Any]] = {}


def _mention_to_star_int(m: Mention) -> int:
    """Map an individual mention/comment sentiment_score (-1..+1) into an App-Store 1..5 star integer."""
    score = float(m.sentiment_score or 0.0)
    sent = (m.sentiment or "neutro").lower()

    if sent == "positivo":
        return 5 if score >= 0.55 else 4
    if sent == "negativo":
        if m.is_crisis_signal or score <= -0.55:
            return 1
        return 2
    # neutro
    if score >= 0.25:
        return 4
    if score <= -0.25:
        return 2
    return 3


def _label_from_stars(stars: float, total: int) -> str:
    if total == 0:
        return "Sem avaliações"
    if stars >= 4.5:
        return "Excelente"
    if stars >= 4.0:
        return "Muito Bom"
    if stars >= 3.3:
        return "Bom com Ressalvas"
    if stars >= 2.5:
        return "Regular"
    if stars >= 1.8:
        return "Atenção"
    return "Crítico"


def _build_deterministic_explanation(
    system_name: str,
    stars: float,
    mentions: list[Mention],
    news_stars: float | None,
    social_stars: float | None,
) -> tuple[str, list[str], list[str]]:
    total = len(mentions)
    if total == 0:
        return (
            f"Ainda não há notícias, publicações ou comentários coletados para {system_name}. Execute uma varredura de sentimento para gerar a nota por estrelas.",
            [],
            [],
        )

    pos = [m for m in mentions if m.sentiment == "positivo"]
    neu = [m for m in mentions if m.sentiment == "neutro"]
    neg = [m for m in mentions if m.sentiment == "negativo"]

    pos_pct = round(len(pos) / total * 100)
    neg_pct = round(len(neg) / total * 100)

    parts = [
        f"{system_name} recebeu {stars:.1f} de 5 estrelas com base em {total} registro(s) analisado(s) "
        f"({pos_pct}% positivos, {round(len(neu) / total * 100)}% neutros e {neg_pct}% negativos)."
    ]
    if news_stars is not None and social_stars is not None:
        parts.append(
            f"Na imprensa/notícias a percepção média é de {news_stars:.1f}★, enquanto nas redes sociais e comentários dos usuários é de {social_stars:.1f}★."
        )

    pos_drivers: list[str] = []
    for m in sorted(pos, key=lambda x: x.sentiment_score, reverse=True)[:3]:
        txt = (m.sentiment_reason or m.summary or m.title).strip()
        if txt and txt not in pos_drivers:
            pos_drivers.append(txt[:160])

    neg_drivers: list[str] = []
    for m in sorted(neg, key=lambda x: x.sentiment_score)[:3]:
        txt = (m.sentiment_reason or m.summary or m.title).strip()
        if txt and txt not in neg_drivers:
            neg_drivers.append(txt[:160])

    return " ".join(parts), pos_drivers, neg_drivers


async def _rate_single_system(
    system: MonitoredSystem,
    mentions: list[Mention],
    runtime_config: dict[str, Any],
    days: int | None = None,
    use_ai: bool = True,
    refresh: bool = False,
) -> dict[str, Any]:
    total = len(mentions)
    latest_id = max((m.id for m in mentions), default=0)
    cache_key = (system.id, total, latest_id, days, use_ai)

    if not refresh and cache_key in _STAR_RATING_CACHE:
        return _STAR_RATING_CACHE[cache_key]

    # 1. Compute exact 1..5 star distribution & channel averages
    star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    news_star_vals: list[int] = []
    social_star_vals: list[int] = []
    pos_count = 0
    neu_count = 0
    neg_count = 0

    for m in mentions:
        s_val = _mention_to_star_int(m)
        star_counts[s_val] += 1
        if m.sentiment == "positivo":
            pos_count += 1
        elif m.sentiment == "negativo":
            neg_count += 1
        else:
            neu_count += 1

        if m.platform in {"news", "web"} and m.content_type != "comment":
            news_star_vals.append(s_val)
        else:
            social_star_vals.append(s_val)

    distribution = [
        {
            "stars": st,
            "count": star_counts[st],
            "pct": round(star_counts[st] / total * 100, 1) if total else 0.0,
        }
        for st in (5, 4, 3, 2, 1)
    ]

    weighted_sum = sum(st * cnt for st, cnt in star_counts.items())
    math_stars = round(weighted_sum / total, 1) if total else 0.0
    news_stars = round(sum(news_star_vals) / len(news_star_vals), 1) if news_star_vals else None
    social_stars = round(sum(social_star_vals) / len(social_star_vals), 1) if social_star_vals else None

    # Default deterministic explanation
    stars = math_stars
    rating_reason, pos_drivers, neg_drivers = _build_deterministic_explanation(
        system.name, stars, mentions, news_stars, social_stars
    )
    analyzed_by = "sentimento_calculado"

    # 2. Gemini AI Synthesis (gives calibrated 1.0..5.0 rating + clear explanation of WHY)
    api_key = runtime_config.get("gemini_api_key", "")
    model = runtime_config.get("gemini_model", "gemini-3.5-flash-lite")

    if use_ai and api_key and total > 0:
        # Select up to 35 representative items (prioritize real comments + negatives + positives)
        comments = [m for m in mentions if m.content_type == "comment"]
        negatives = [m for m in mentions if m.sentiment == "negativo" and m not in comments]
        others = [m for m in mentions if m not in comments and m not in negatives]
        sample = (comments[:18] + negatives[:10] + others[:15])[:35]

        sample_payload = [
            {
                "tipo": "comentário" if m.content_type == "comment" else ("notícia" if m.platform == "news" else "post"),
                "plataforma": m.platform,
                "sentimento": m.sentiment,
                "score": m.sentiment_score,
                "autor": m.author[:40],
                "texto": (m.content or m.title)[:260],
                "motivo": (m.sentiment_reason or m.summary)[:180],
            }
            for m in sample
        ]

        prompt = f"""Você é um avaliador de reputação de aplicativos e sistemas públicos (estilo Google Play Store / Apple App Store).
Avalie o projeto "{system.name}" ({system.citizen_area} — {system.organization_type}) com uma nota de 1.0 a 5.0 estrelas baseada EXCLUSIVAMENTE nas notícias, publicações e comentários reais abaixo.

RESUMO NUMÉRICO DOS DADOS REAIS:
- Total de itens analisados: {total} ({pos_count} positivos, {neu_count} neutros, {neg_count} negativos)
- Média matemática das estrelas: {math_stars:.1f}★ (distribuição: 5★={star_counts[5]}, 4★={star_counts[4]}, 3★={star_counts[3]}, 2★={star_counts[2]}, 1★={star_counts[1]})
- Média em notícias/mídia: {f"{news_stars:.1f}★ ({len(news_star_vals)} itens)" if news_stars is not None else "sem notícias"}
- Média em redes sociais/comentários: {f"{social_stars:.1f}★ ({len(social_star_vals)} itens)" if social_stars is not None else "sem redes sociais"}

AMOSTRA DAS NOTÍCIAS E COMENTÁRIOS REAIS:
{json.dumps(sample_payload, ensure_ascii=False)}

REGRAS:
- Dê uma nota coerente entre 1.0 e 5.0 (1 casa decimal), levando em conta tanto a cobertura positiva quanto o peso real das críticas de usuários nos comentários.
- Explique em português claro e objetivo POR QUE o projeto recebeu essa nota de estrelas (2 a 3 frases diretas citando fatos concretos das notícias e comentários).
- Liste de 1 a 3 pontos positivos que elevaram as estrelas e de 0 a 3 pontos negativos/ressalvas que puxaram a nota para baixo (se não houver pontos negativos reais, retorne lista vazia []).

Retorne EXCLUSIVAMENTE um JSON válido:
{{
  "stars": 4.2,
  "rating_label": "Muito Bom",
  "rating_reason": "Explicação clara de 2 a 3 frases dizendo exatamente por que o projeto recebeu essa nota.",
  "positive_drivers": ["Ponto positivo concreto 1", "Ponto positivo concreto 2"],
  "negative_drivers": ["Ponto negativo/crítica real 1"]
}}
"""
        output_text, _, error = await asyncio.to_thread(
            call_gemini_interaction,
            api_key,
            prompt,
            model,
            False,
            "Você é um analista sênior de experiência do cidadão e avaliação de apps públicos. Responda apenas em JSON válido.",
        )
        parsed = extract_json_payload(output_text) if output_text else None
        if not error and isinstance(parsed, dict) and parsed.get("rating_reason"):
            try:
                ai_stars = float(parsed.get("stars", math_stars))
                # Keep AI rating grounded within ±0.6 of the math average and within [1.0, 5.0]
                clamped = max(1.0, min(5.0, ai_stars))
                if abs(clamped - math_stars) > 0.65:
                    clamped = max(1.0, min(5.0, math_stars + (0.6 if clamped > math_stars else -0.6)))
                stars = round(clamped, 1)
            except (TypeError, ValueError):
                stars = math_stars
            rating_reason = str(parsed.get("rating_reason") or rating_reason).strip()[:600]
            raw_pos = parsed.get("positive_drivers")
            raw_neg = parsed.get("negative_drivers")
            if isinstance(raw_pos, list):
                pos_drivers = [str(x).strip()[:200] for x in raw_pos if str(x).strip()][:3]
            if isinstance(raw_neg, list):
                neg_drivers = [str(x).strip()[:200] for x in raw_neg if str(x).strip()][:3]
            analyzed_by = model

    result = {
        "system_id": system.id,
        "system_name": system.name,
        "citizen_area": system.citizen_area,
        "stars": stars,
        "rating_label": _label_from_stars(stars, total),
        "total_mentions": total,
        "positive_count": pos_count,
        "neutral_count": neu_count,
        "negative_count": neg_count,
        "news_stars": news_stars,
        "news_count": len(news_star_vals),
        "social_stars": social_stars,
        "social_count": len(social_star_vals),
        "star_distribution": distribution,
        "rating_reason": rating_reason,
        "positive_drivers": pos_drivers,
        "negative_drivers": neg_drivers,
        "analyzed_by": analyzed_by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _STAR_RATING_CACHE[cache_key] = result
    return result


async def build_project_star_ratings(
    db: Session,
    system_id: int | None = None,
    days: int | None = None,
    use_ai: bool = True,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Compute App-Store-style 5-star reputation ratings for one or all active systems."""
    q_sys = db.query(MonitoredSystem).filter(MonitoredSystem.is_active == True)  # noqa: E712
    if system_id is not None:
        q_sys = q_sys.filter(MonitoredSystem.id == system_id)
    systems = q_sys.order_by(MonitoredSystem.id.asc()).all()
    if not systems:
        return []

    runtime_config = get_runtime_config(db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(days)) if days else None

    tasks = []
    for sys_obj in systems:
        m_rows = db.query(Mention).filter(Mention.system_id == sys_obj.id).all()
        if cutoff is not None:
            m_rows = [m for m in m_rows if mention_timestamp(m) >= cutoff]
        tasks.append(_rate_single_system(sys_obj, m_rows, runtime_config, days=days, use_ai=use_ai, refresh=refresh))

    ratings = await asyncio.gather(*tasks)
    ratings.sort(key=lambda r: (r["total_mentions"] > 0, r["stars"], r["total_mentions"]), reverse=True)
    return ratings
