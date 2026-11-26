from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_runtime_config
from app.models import Mention, MonitoredSystem
from app.services.gemini_client import call_gemini_interaction, extract_json_payload
from app.services.temporal import SOCIAL_PLATFORMS, mention_timestamp

logger = logging.getLogger(__name__)


FRICTION_PATTERNS = [
    r"erro", r"bug", r"falha", r"não consigo", r"nao consigo", r"não funciona", r"nao funciona",
    r"fora do ar", r"caiu", r"indispon[ií]vel", r"lent[oa]", r"lentid[aã]o", r"trava", r"travando",
    r"carregando", r"demora", r"login", r"senha", r"acesso", r"bloquead", r"dificuldade",
    r"como fa[cç]o", r"algu[eé]m sabe", r"ajuda", r"suporte", r"ningu[eé]m responde",
    r"n[aã]o abre", r"n[aã]o carrega", r"n[aã]o salva", r"perdi", r"apagou", r"confuso",
    r"complicado", r"p[eé]ssimo", r"horr[ií]vel", r"reclama", r"problema", r"\?",
]

PROBLEM_TAXONOMY: list[dict[str, Any]] = [
    {
        "id": "outage",
        "title": "Indisponibilidade e quedas do sistema",
        "category": "Estabilidade / Infraestrutura",
        "action_type": "tecnica",
        "base_severity": "critica",
        "keywords": [
            "fora do ar", "caiu", "erro 500", "erro 502", "erro 503", "erro 504",
            "indisponível", "indisponivel", "servidor", "não abre", "nao abre", "manutenção",
            "outage", "down",
        ],
        "description": "Usuários relatam que o sistema ficou inacessível, retornou erros de servidor ou saiu do ar durante o uso.",
        "recommended_action": "Revisar monitoramento de disponibilidade, capacidade em horários de pico (ex.: fechamento de bimestre/prazos) e criar página de status ou aviso proativo nas redes.",
    },
    {
        "id": "auth_login",
        "title": "Problemas de login, senha e acesso",
        "category": "Login e Autenticação",
        "action_type": "tecnica",
        "base_severity": "alta",
        "keywords": [
            "login", "senha", "entrar", "acesso", "acessar", "bloqueado", "bloqueada",
            "gov.br", "cadastro", "cpf", "masp", "token", "autenticação", "autenticacao",
            "não consigo entrar", "nao consigo entrar", "esqueci",
        ],
        "description": "Cidadãos ou servidores enfrentam barreiras para autenticar, recuperar senha ou concluir o acesso à conta.",
        "recommended_action": "Simplificar o fluxo de recuperação de senha, exibir mensagens de erro mais claras na tela de login e publicar guia rápido nos canais oficiais.",
    },
    {
        "id": "performance",
        "title": "Lentidão, travamentos e demora no carregamento",
        "category": "Desempenho / Performance",
        "action_type": "tecnica",
        "base_severity": "alta",
        "keywords": [
            "lento", "lenta", "lentidão", "lentidao", "trava", "travando", "travado",
            "carregando", "infinito", "demora", "demorado", "pesado", "congelou", "slow",
        ],
        "description": "Relatos de tempo excessivo de resposta, telas congelando ou carregamento infinito durante operações do dia a dia.",
        "recommended_action": "Mapear consultas/rotas mais lentas no backend, aplicar cache/otimização em operações em lote e testar desempenho em conexões móveis 3G/4G.",
    },
    {
        "id": "functional_bugs",
        "title": "Erros ao salvar, enviar documentos ou lançar registros",
        "category": "Bugs Funcionais",
        "action_type": "tecnica",
        "base_severity": "alta",
        "keywords": [
            "erro", "bug", "falha", "não salva", "nao salva", "apagou", "sumiu", "perdi",
            "upload", "pdf", "anexar", "nota", "notas", "frequência", "frequencia",
            "chamada", "fechamento", "bimestre", "protocolo", "agendamento", "salvar",
            "não funciona", "nao funciona", "quebrado",
        ],
        "description": "Usuários relatam falhas funcionais ao concluir tarefas centrais do sistema (salvar dados, anexar arquivos, lançar registros ou concluir solicitações).",
        "recommended_action": "Reproduzir os fluxos críticos citados nos comentários (especialmente Safari/mobile), adicionar salvamento automático/rascunho e priorizar hotfix na sprint.",
    },
    {
        "id": "usability_mobile",
        "title": "Dificuldade de uso, navegação confusa ou problemas no celular",
        "category": "Usabilidade / UX & Mobile",
        "action_type": "ux",
        "base_severity": "media",
        "keywords": [
            "confuso", "complicado", "difícil", "dificil", "não achei", "nao achei",
            "menu", "interface", "celular", "mobile", "safari", "iphone", "android",
            "tela", "botão", "botao", "acessibilidade", "idoso", "burocrático",
        ],
        "description": "Usuários relatam dificuldade para localizar menus, entender etapas do fluxo ou utilizar o sistema confortavelmente pelo celular.",
        "recommended_action": "Realizar revisão de UX mobile-first nos fluxos mais reclamados, destacar atalhos principais na tela inicial e validar com usuários reais.",
    },
    {
        "id": "support_response",
        "title": "Falta de retorno do suporte e canais de atendimento",
        "category": "Atendimento / Suporte",
        "action_type": "suporte",
        "base_severity": "media",
        "keywords": [
            "suporte", "atendimento", "ninguém responde", "ninguem responde", "chamado",
            "ouvidoria", "descaso", "sem resposta", "telefone", "e-mail", "retorno",
        ],
        "description": "Usuários reclamam de demora ou ausência de resposta ao acionar o suporte técnico ou canais institucionais.",
        "recommended_action": "Estruturar respostas rápidas nas redes sociais (Instagram/Facebook) com link direto para FAQ/suporte e monitorar SLA de chamados críticos.",
    },
    {
        "id": "security_privacy",
        "title": "Preocupações com segurança, privacidade ou dados incorretos",
        "category": "Segurança / LGPD",
        "action_type": "tecnica",
        "base_severity": "critica",
        "keywords": [
            "vazamento", "dados", "lgpd", "segurança", "seguranca", "golpe", "fraude",
            "privacidade", "hackeado", "inseguro", "errado", "duplicado",
        ],
        "description": "Menções envolvendo segurança da informação, integridade de registros ou suspeitas de fraude/vazamento.",
        "recommended_action": "Acionar imediatamente equipe de segurança/DPO para validar integridade dos dados e emitir nota oficial esclarecedora se necessário.",
    },
    {
        "id": "guidance_doubts",
        "title": "Dúvidas operacionais e falta de orientação/tutoriais",
        "category": "Comunicação / Orientação",
        "action_type": "comunicacao",
        "base_severity": "baixa",
        "keywords": [
            "como faço", "como faco", "alguém sabe", "alguem sabe", "dúvida", "duvida",
            "onde fica", "quando abre", "tutorial", "manual", "ajuda", "explica", "?",
        ],
        "description": "Comentários de usuários buscando orientação prática sobre como usar recursos, prazos ou onde encontrar determinada função.",
        "recommended_action": "Criar carrosséis/Reels curtos no Instagram e Facebook respondendo às dúvidas mais frequentes e fixar nos destaques do perfil oficial.",
    },
]


def _is_friction_item(m: Mention) -> bool:
    if m.sentiment == "negativo" or m.is_crisis_signal:
        return True
    if m.sentiment == "neutro":
        text = f"{m.title} {m.content} {m.summary}".lower()
        return any(re.search(pat, text) for pat in FRICTION_PATTERNS)
    return False


def _filter_by_channel_group(mentions: list[Mention], channel_group: str) -> list[Mention]:
    if channel_group == "instagram_facebook":
        return [m for m in mentions if (m.platform or "").lower() in {"instagram", "facebook"}]
    if channel_group == "redes_sociais":
        return [m for m in mentions if (m.platform or "").lower() in SOCIAL_PLATFORMS]
    if channel_group == "internet":
        return [m for m in mentions if (m.platform or "").lower() not in SOCIAL_PLATFORMS]
    return mentions


def _classify_local(m: Mention) -> str:
    text = f"{m.title} {m.content} {m.summary} {m.topics_json}".lower()
    best_id = "guidance_doubts" if m.sentiment == "neutro" else "functional_bugs"
    best_hits = 0
    for rule in PROBLEM_TAXONOMY:
        hits = sum(1 for kw in rule["keywords"] if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_id = rule["id"]
    return best_id


def _severity_rank(sev: str) -> int:
    return {"critica": 4, "alta": 3, "media": 2, "baixa": 1}.get(sev, 1)


def _format_evidence(m: Mention, system_map: dict[int, str]) -> dict[str, Any]:
    return {
        "id": m.id,
        "system_name": system_map.get(m.system_id, ""),
        "platform": m.platform,
        "content_type": getattr(m, "content_type", "mention") or "mention",
        "author": m.author,
        "title": m.title,
        "excerpt": (m.content or m.summary or m.title)[:280],
        "url": m.url or getattr(m, "parent_post_url", "") or "",
        "sentiment": m.sentiment,
        "sentiment_score": m.sentiment_score,
        "is_crisis_signal": m.is_crisis_signal,
        "date": (m.published_at or m.collected_at).isoformat() if (m.published_at or m.collected_at) else "",
    }


def _build_local_clusters(
    current_friction: list[Mention],
    prev_friction: list[Mention],
    system_map: dict[int, str],
) -> tuple[list[dict[str, Any]], str]:
    grouped: dict[str, list[Mention]] = defaultdict(list)
    for m in current_friction:
        grouped[_classify_local(m)].append(m)

    prev_counts: Counter[str] = Counter(_classify_local(m) for m in prev_friction)
    rule_by_id = {r["id"]: r for r in PROBLEM_TAXONOMY}
    total_friction = max(1, len(current_friction))

    clusters: list[dict[str, Any]] = []
    for pid, items in grouped.items():
        rule = rule_by_id[pid]
        count = len(items)
        prev_c = prev_counts.get(pid, 0)
        has_crisis = any(m.is_crisis_signal for m in items)
        avg_score = round(sum(m.sentiment_score for m in items) / count, 2)

        severity = rule["base_severity"]
        if has_crisis and severity != "critica":
            severity = "critica"
        elif count >= 4 and severity == "media":
            severity = "alta"

        if prev_c == 0 and count > 0:
            trend = "novo"
        elif count > prev_c:
            trend = "subindo"
        elif count < prev_c:
            trend = "caindo"
        else:
            trend = "estavel"

        plat_counts = Counter((m.platform or "web").lower() for m in items)
        items_sorted = sorted(items, key=lambda x: (x.is_crisis_signal, -x.sentiment_score), reverse=True)

        clusters.append(
            {
                "id": pid,
                "title": rule["title"],
                "category": rule["category"],
                "severity": severity,
                "action_type": rule["action_type"],
                "mentions_count": count,
                "share_pct": round((count / total_friction) * 100, 1),
                "avg_sentiment": avg_score,
                "trend": trend,
                "platforms": [{"platform": p, "count": c} for p, c in plat_counts.most_common()],
                "description": rule["description"],
                "recommended_action": rule["recommended_action"],
                "evidences": [_format_evidence(m, system_map) for m in items_sorted[:5]],
            }
        )

    clusters.sort(key=lambda c: (_severity_rank(c["severity"]), c["mentions_count"]), reverse=True)

    if not clusters:
        exec_summary = "Nenhum problema ou reclamação relevante detectado neste recorte. Continue coletando comentários do Instagram/Facebook e menções na web para manter o diagnóstico atualizado."
    else:
        top = clusters[0]
        exec_summary = (
            f"Foram identificados {len(clusters)} grupos de problemas a partir de {len(current_friction)} relatos/comentários de atrito. "
            f"A principal dor atual é \"{top['title']}\" ({top['mentions_count']} relato(s), {top['share_pct']}% das queixas, severidade {top['severity']})."
        )

    return clusters, exec_summary


async def _cluster_with_gemini(
    system_name: str,
    current_friction: list[Mention],
    system_map: dict[int, str],
    runtime_config: dict[str, Any],
) -> tuple[list[dict[str, Any]] | None, str | None]:
    api_key = runtime_config.get("gemini_api_key", "")
    if not api_key or len(current_friction) < 2:
        return None, None

    model = runtime_config.get("gemini_model", "gemini-4-hydrogen")
    by_id = {m.id: m for m in current_friction}
    payload_items = [
        {
            "id": m.id,
            "platform": m.platform,
            "type": getattr(m, "content_type", "mention") or "mention",
            "sentiment": m.sentiment,
            "text": f"{m.title}. {m.content}"[:400],
        }
        for m in current_friction[:60]
    ]

    prompt = f"""Você é um especialista sênior em Produto Digital, UX e Engenharia de Sistemas Públicos.
Analise os comentários e menções de usuários/cidadãos abaixo sobre "{system_name}" e agrupe os PROBLEMAS CONCRETOS que estão incomodando os usuários.

RELATOS COLETADOS:
{json.dumps(payload_items, ensure_ascii=False)}

Retorne EXCLUSIVAMENTE um JSON válido no formato:
{{
  "executive_summary": "Resumo executivo direto de 2 frases em português sobre os principais gargalos sentidos pelos usuários e o que atacar primeiro.",
  "problems": [
    {{
      "id": "slug_curto",
      "title": "Título objetivo do problema real (ex: Travamento ao lançar frequência no celular)",
      "category": "Estabilidade | Login e Acesso | Desempenho | Bug Funcional | Usabilidade/Mobile | Suporte | Comunicação/Dúvidas | Segurança/LGPD",
      "severity": "critica" | "alta" | "media" | "baixa",
      "action_type": "tecnica" | "ux" | "comunicacao" | "suporte",
      "description": "Diagnóstico objetivo do problema percebido nos comentários",
      "recommended_action": "Ação prática e específica recomendada para a equipe resolver ou mitigar",
      "mention_ids": [1, 2]
    }}
  ]
}}
Agrupe em 2 a 6 problemas distintos, ordenados do mais grave/frequente para o menos grave. Use APENAS mention_ids presentes na lista fornecida.
"""

    output_text, _, error = await asyncio.to_thread(
        call_gemini_interaction,
        api_key,
        prompt,
        model,
        False,
        "Responda somente em JSON válido em português do Brasil.",
    )
    if error or not output_text:
        return None, None

    parsed = extract_json_payload(output_text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("problems"), list):
        return None, None

    total = max(1, len(current_friction))
    clusters: list[dict[str, Any]] = []
    for raw in parsed["problems"]:
        if not isinstance(raw, dict):
            continue
        mids = [int(mid) for mid in (raw.get("mention_ids") or []) if int(mid) in by_id]
        if not mids:
            continue
        items = [by_id[mid] for mid in mids]
        plat_counts = Counter((m.platform or "web").lower() for m in items)
        sev = str(raw.get("severity", "media")).lower()
        if sev not in {"critica", "alta", "media", "baixa"}:
            sev = "media"
        act = str(raw.get("action_type", "tecnica")).lower()
        if act not in {"tecnica", "ux", "comunicacao", "suporte"}:
            act = "tecnica"

        clusters.append(
            {
                "id": str(raw.get("id") or f"prob-{len(clusters)+1}")[:50],
                "title": str(raw.get("title") or "Problema relatado")[:160],
                "category": str(raw.get("category") or "Geral")[:80],
                "severity": sev,
                "action_type": act,
                "mentions_count": len(items),
                "share_pct": round((len(items) / total) * 100, 1),
                "avg_sentiment": round(sum(m.sentiment_score for m in items) / len(items), 2),
                "trend": "estavel",
                "platforms": [{"platform": p, "count": c} for p, c in plat_counts.most_common()],
                "description": str(raw.get("description") or "")[:500],
                "recommended_action": str(raw.get("recommended_action") or "")[:500],
                "evidences": [_format_evidence(m, system_map) for m in items[:5]],
            }
        )

    if not clusters:
        return None, None

    clusters.sort(key=lambda c: (_severity_rank(c["severity"]), c["mentions_count"]), reverse=True)
    return clusters, str(parsed.get("executive_summary") or "")


async def build_problem_diagnostics(
    db: Session,
    system_id: int | None = None,
    days: int | None = 365,
    channel_group: str = "all",
    use_ai: bool = True,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    runtime_config = get_runtime_config(db)

    system_name = "Todos os sistemas"
    q = db.query(Mention)
    if system_id is not None:
        q = q.filter(Mention.system_id == system_id)
        sys_obj = db.query(MonitoredSystem).filter(MonitoredSystem.id == system_id).first()
        if sys_obj:
            system_name = sys_obj.name

    all_mentions = _filter_by_channel_group(q.all(), channel_group)
    system_map = {s.id: s.name for s in db.query(MonitoredSystem.id, MonitoredSystem.name).all()}

    if days is not None:
        cutoff = now - timedelta(days=days)
        prev_cutoff = now - timedelta(days=days * 2)
        current_items = [m for m in all_mentions if mention_timestamp(m) >= cutoff]
        prev_items = [m for m in all_mentions if prev_cutoff <= mention_timestamp(m) < cutoff]
    else:
        current_items = all_mentions
        prev_items = []

    current_friction = [m for m in current_items if _is_friction_item(m)]
    prev_friction = [m for m in prev_items if _is_friction_item(m)]

    analyzed_mode = "local_rules"
    clusters: list[dict[str, Any]] | None = None
    exec_summary: str | None = None

    if use_ai and runtime_config.get("gemini_api_key") and len(current_friction) >= 2:
        clusters, exec_summary = await _cluster_with_gemini(
            system_name, current_friction, system_map, runtime_config
        )
        if clusters:
            analyzed_mode = runtime_config.get("gemini_model", "gemini-4-hydrogen")

    if not clusters:
        clusters, exec_summary = _build_local_clusters(current_friction, prev_friction, system_map)

    plat_counts = Counter((m.platform or "web").lower() for m in current_friction)
    top_channel = plat_counts.most_common(1)[0][0] if plat_counts else "nenhum"
    critical_or_high = sum(1 for c in clusters if c["severity"] in {"critica", "alta"})
    comments_analyzed = sum(1 for m in current_items if (getattr(m, "content_type", "") == "comment"))

    return {
        "system_id": system_id,
        "system_name": system_name,
        "days": days,
        "channel_group": channel_group,
        "total_mentions_analyzed": len(current_items),
        "total_comments_analyzed": comments_analyzed,
        "total_friction_mentions": len(current_friction),
        "problems_count": len(clusters),
        "critical_or_high_count": critical_or_high,
        "top_complaint_channel": top_channel,
        "analyzed_by": analyzed_mode,
        "executive_summary": exec_summary or "",
        "problems": clusters,
    }
