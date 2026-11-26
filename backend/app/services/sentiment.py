from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.services.gemini_client import call_gemini_interaction, extract_json_payload

logger = logging.getLogger(__name__)

POSITIVE_WORDS = {
    "excelente", "ótimo", "otimo", "bom", "boa", "parabéns", "parabens", "rápido", "rapido",
    "eficiente", "prático", "pratico", "fácil", "facil", "resolveu", "ajudou", "maravilhoso",
    "sensacional", "inovador", "inovação", "inovacao", "transparência", "transparencia",
    "premiado", "destaque", "sucesso", "elogiado", "aprovado", "melhoria", "moderno",
    "agilidade", "ágil", "agil", "recomendo", "funciona bem", "great", "excellent", "helpful",
    "fast", "awesome", "love", "award", "praised", "improved",
}

NEGATIVE_WORDS = {
    "péssimo", "pessimo", "horrível", "horrivel", "ruim", "lento", "lentidão", "lentidao",
    "travando", "trava", "erro", "erros", "bug", "bugs", "falha", "falhando", "indisponível",
    "indisponivel", "fora do ar", "caiu", "não funciona", "nao funciona", "absurdo",
    "vergonha", "descaso", "reclamação", "reclamacao", "insatisfeito", "problema", "problemas",
    "complicado", "confuso", "pior", "golpe", "vazamento", "inseguro", "quebrado",
    "demora", "demorado", "burocrático", "burocratico", "terrible", "broken", "slow", "crash",
    "worst", "down", "outage", "failed", "scam", "leak",
}

CRISIS_PATTERNS = [
    r"fora do ar",
    r"vazamento de dados",
    r"hackead[oa]",
    r"golpe",
    r"fraude",
    r"sistema caiu",
    r"não funciona há dias",
    r"indisponível",
    r"data breach",
    r"major outage",
]

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "desempenho": ["lento", "lentidão", "trava", "travando", "caiu", "fora do ar", "rápido", "agilidade", "slow", "fast"],
    "usabilidade": ["interface", "fácil", "difícil", "confuso", "prático", "intuitivo", "design", "ux", "navegação"],
    "atendimento": ["atendimento", "cidadão", "suporte", "resposta", "fila", "agendamento", "protocolo", "ouvidoria"],
    "bug/estabilidade": ["erro", "bug", "falha", "crash", "tela branca", "não carrega", "não abre", "login"],
    "segurança/privacidade": ["dados", "vazamento", "lgpd", "senha", "gov.br", "segurança", "privacidade", "fraude"],
    "acessibilidade": ["acessibilidade", "idoso", "libras", "leitor de tela", "inclusão", "celular"],
    "inovação/reconhecimento": ["prêmio", "inovação", "ia", "inteligência artificial", "modernização", "referência"],
}


def _extract_best_quote(title: str, content: str, matched_terms: list[str]) -> str:
    """Pick the most relevant sentence/excerpt containing the matched sentiment terms."""
    source = (content or title or "").strip()
    if not source:
        return ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", source) if s.strip()]
    if matched_terms and sentences:
        for sent in sentences:
            low = sent.lower()
            if any(t in low for t in matched_terms):
                return sent[:240] + ("…" if len(sent) > 240 else "")
    first = sentences[0] if sentences else source
    return first[:240] + ("…" if len(first) > 240 else "")


def analyze_sentiment_lexicon(title: str, content: str) -> dict[str, Any]:
    """Deterministic local fallback sentiment analyzer (PT-BR + EN) with explanation and verbatim quote."""
    text = f"{title} {content}".lower()
    pos_matched = [w for w in POSITIVE_WORDS if w in text]
    neg_matched = [w for w in NEGATIVE_WORDS if w in text]
    pos_hits = len(pos_matched)
    neg_hits = len(neg_matched)

    # Check explicit crisis patterns
    crisis_matched = [pat for pat in CRISIS_PATTERNS if re.search(pat, text)]
    is_crisis = bool(crisis_matched)
    if is_crisis:
        neg_hits += 2

    total = pos_hits + neg_hits
    if total == 0:
        score = 0.0
        sentiment = "neutro"
        confidence = 0.55
        reason = "Texto informativo, tutorial ou pergunta sem adjetivos fortes de elogio ou crítica."
        quote = _extract_best_quote(title, content, [])
    else:
        score = round((pos_hits - neg_hits) / max(total, 2), 2)
        score = max(-1.0, min(1.0, score))
        if score >= 0.2:
            sentiment = "positivo"
            terms_str = ", ".join(f"'{w}'" for w in pos_matched[:4])
            reason = f"Classificado como positivo por destacar termos favoráveis ({terms_str})."
            quote = _extract_best_quote(title, content, pos_matched)
        elif score <= -0.2:
            sentiment = "negativo"
            terms_str = ", ".join(f"'{w}'" for w in neg_matched[:4]) or "sinal de indisponibilidade/falha"
            reason = f"Classificado como negativo por relatar críticas ou problemas ({terms_str})."
            quote = _extract_best_quote(title, content, neg_matched)
        else:
            sentiment = "neutro"
            reason = "Tom misto ou equilibrado entre menções positivas e ressalvas/dúvidas."
            quote = _extract_best_quote(title, content, neg_matched + pos_matched)
        confidence = round(min(0.88, 0.55 + 0.08 * total), 2)

    topics = []
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in kws):
            topics.append(topic)
    if not topics:
        topics = ["menção geral"]

    clean_summary = (title or content).strip()
    if len(clean_summary) > 180:
        clean_summary = clean_summary[:177] + "..."

    return {
        "sentiment": sentiment,
        "sentiment_score": score,
        "confidence": confidence,
        "topics": topics[:4],
        "summary": clean_summary,
        "sentiment_reason": reason,
        "evidence_quote": quote,
        "is_crisis_signal": is_crisis or score <= -0.75,
        "analyzed_by": "lexicon",
    }


async def analyze_mentions_batch(
    system_name: str,
    system_description: str,
    items: list[dict[str, str]],
    runtime_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Analyze sentiment for a batch of mentions using Gemini API or local lexicon fallback."""
    if not items:
        return []

    api_key = runtime_config.get("gemini_api_key", "")
    model = runtime_config.get("gemini_model", "gemini-4-hydrogen")

    if not api_key:
        return [analyze_sentiment_lexicon(it.get("title", ""), it.get("content", "")) for it in items]

    results: list[dict[str, Any]] = []
    batch_size = 12
    for i in range(0, len(items), batch_size):
        chunk = items[i : i + batch_size]
        serialized = [
            {
                "idx": idx,
                "platform": it.get("platform", "web"),
                "content_type": it.get("content_type", "mention"),
                "title": it.get("title", "")[:250],
                "content": it.get("content", "")[:600],
            }
            for idx, it in enumerate(chunk)
        ]

        prompt = f"""Analise o sentimento e a RELEVÂNCIA das menções/comentários abaixo referentes ao sistema "{system_name}".
Descrição do sistema: {system_description[:400]}

REGRA CRÍTICA DE RELEVÂNCIA (especialmente para content_type="comment"):
- Marque "is_relevant": true SOMENTE se o texto falar diretamente do sistema "{system_name}", de suas funcionalidades, uso, usabilidade, desempenho, erros, tecnologia/IA ou impacto direto no trabalho/atendimento.
- Marque "is_relevant": false se o comentário aproveitar a postagem para reclamar de OUTROS assuntos sem ligação com o software (ex.: piso salarial, aumento de salário, pagamento/Fundeb sem citar o sistema, concurso, designação, saneamento básico, merenda, política geral) OU for apenas emoji/reação vaga sem relação clara com o sistema.

MENÇÕES:
{json.dumps(serialized, ensure_ascii=False)}

Retorne EXCLUSIVAMENTE um JSON válido com a lista "results" na mesma ordem dos índices (0..{len(chunk)-1}):
{{
  "results": [
    {{
      "idx": 0,
      "is_relevant": true se falar diretamente deste sistema/software/funcionalidade, ou false se for fora de tema (ex.: piso salarial/política geral sem relação com o sistema, esporte, outra sigla, outro estado),
      "sentiment": "positivo" | "neutro" | "negativo",
      "sentiment_score": número float entre -1.0 (muito negativo) e 1.0 (muito positivo),
      "confidence": número float entre 0.0 e 1.0,
      "topics": ["lista", "de", "2 a 4", "temas curtos em português"],
      "summary": "Resumo objetivo de 1 frase em português do ponto levantado pelo cidadão/mídia",
      "sentiment_reason": "Explicação clara de 1 frase em português dizendo POR QUE este texto é positivo, neutro ou negativo",
      "evidence_quote": "Trecho literal exato (até 220 caracteres) copiado do texto/comentário que comprova essa classificação",
      "is_crisis_signal": true se indicar indisponibilidade grave, vazamento/LGPD, fraude, reclamação viral ou falha crítica no atendimento ao cidadão, senão false
    }}
  ]
}}
"""
        output_text, _, error = await asyncio.to_thread(
            call_gemini_interaction,
            api_key,
            prompt,
            model,
            False,
            "Você é um especialista em análise de sentimento de serviços públicos digitais e experiência do cidadão. Responda apenas em JSON válido.",
        )

        parsed = extract_json_payload(output_text) if output_text else None
        raw_list = parsed.get("results", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])

        if error or len(raw_list) != len(chunk):
            logger.warning("Falling back to lexicon sentiment for chunk (error=%s)", error)
            for it in chunk:
                results.append(analyze_sentiment_lexicon(it.get("title", ""), it.get("content", "")))
            continue

        by_idx = {int(r.get("idx", idx)): r for idx, r in enumerate(raw_list) if isinstance(r, dict)}
        for idx, it in enumerate(chunk):
            r = by_idx.get(idx)
            if not r:
                results.append(analyze_sentiment_lexicon(it.get("title", ""), it.get("content", "")))
                continue
            sentiment = str(r.get("sentiment", "neutro")).lower()
            if sentiment not in {"positivo", "neutro", "negativo"}:
                sentiment = "neutro"
            try:
                score = max(-1.0, min(1.0, float(r.get("sentiment_score", 0.0))))
            except (TypeError, ValueError):
                score = 0.0
            try:
                conf = max(0.0, min(1.0, float(r.get("confidence", 0.8))))
            except (TypeError, ValueError):
                conf = 0.8
            topics = r.get("topics") if isinstance(r.get("topics"), list) else ["menção geral"]
            fallback_quote = _extract_best_quote(it.get("title", ""), it.get("content", ""), [])
            results.append(
                {
                    "is_relevant": bool(r.get("is_relevant", True)),
                    "sentiment": sentiment,
                    "sentiment_score": round(score, 2),
                    "confidence": round(conf, 2),
                    "topics": [str(t)[:40] for t in topics[:4]],
                    "summary": str(r.get("summary") or it.get("title", ""))[:300],
                    "sentiment_reason": str(r.get("sentiment_reason") or r.get("summary") or "")[:360],
                    "evidence_quote": str(r.get("evidence_quote") or fallback_quote)[:260],
                    "is_crisis_signal": bool(r.get("is_crisis_signal", False)),
                    "analyzed_by": model,
                }
            )

    return results
