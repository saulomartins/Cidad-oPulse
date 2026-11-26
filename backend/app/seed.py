from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import AwardOpportunity, Mention, MonitoredSystem
from app.services.awards_radar import (
    CURATED_GLOBAL_AWARDS,
    _award_fingerprint,
    _score_curated_award,
    next_annual_date,
)


def seed_initial_data(db: Session) -> None:
    """Populate realistic starter examples if database is completely empty."""
    if db.query(MonitoredSystem).count() > 0:
        return

    now = datetime.now(timezone.utc)

    sys1 = MonitoredSystem(
        name="Portal Cidadão Digital 360",
        slug="portal-cidadao-digital-360",
        description=(
            "Plataforma unificada de serviços públicos digitais que permite ao cidadão agendar consultas na rede pública, "
            "emitir certidões, acompanhar protocolos de ouvidoria e tirar dúvidas 24h com assistente de IA conversacional em linguagem simples."
        ),
        urls_json=json.dumps(["https://cidadao360.exemplo.gov.br", "https://app.cidadao360.exemplo.gov.br"]),
        keywords_json=json.dumps(["Portal Cidadão Digital 360", "Cidadao360", "#Cidadao360", "atendimento digital prefeitura"]),
        stage="producao",
        uses_ai="com_ia",
        ai_details="Assistente conversacional com IA generativa para triagem de solicitações, leitura de documentos e atendimento acessível em áudio/texto.",
        citizen_area="Serviços Públicos Digitais",
        target_audience="Cidadãos urbanos, idosos e população de baixa renda que dependem de serviços municipais",
        organization_type="Governo Municipal",
        country="Brasil",
        impact_summary="Redução de 62% no tempo médio de atendimento presencial e mais de 180 mil protocolos resolvidos digitalmente.",
        monitor_sentiment=True,
        monitor_awards=True,
        is_active=True,
    )

    sys2 = MonitoredSystem(
        name="FilaZero Saúde Aberta",
        slug="filazero-saude-aberta",
        description=(
            "Iniciativa de software aberto (sem IA) para transparência em tempo real das filas de exames, vacinas e consultas "
            "nas unidades básicas de saúde, enviando avisos por SMS/WhatsApp e evitando deslocamentos desnecessários do cidadão."
        ),
        urls_json=json.dumps(["https://filazero.exemplo.org.br"]),
        keywords_json=json.dumps(["FilaZero Saúde", "FilaZero", "transparência fila SUS"]),
        stage="iniciativa",
        uses_ai="sem_ia",
        ai_details="",
        citizen_area="Saúde",
        target_audience="Pacientes da rede pública de saúde e gestores municipais",
        organization_type="Iniciativa Cívica / Governo Municipal",
        country="Brasil",
        impact_summary="Protótipo em piloto com 12 UBS visando zerar faltas não avisadas e dar previsibilidade total ao paciente.",
        monitor_sentiment=True,
        monitor_awards=True,
        is_active=True,
    )

    db.add_all([sys1, sys2])
    db.commit()
    db.refresh(sys1)
    db.refresh(sys2)

    # Starter sample mentions so charts and filters render immediately on first load
    sample_mentions = [
        (sys1.id, "seed", "news", "Portal Cidadão Digital 360 reduz filas de atendimento em 60%", "Matéria destaca rapidez na emissão de certidões e boa aceitação do assistente digital pelos moradores.", "https://noticias.exemplo.gov.br/cidadao-360", "Portal Local News", "Portal Cidadão Digital 360", now - timedelta(days=5), "positivo", 0.84, 0.92, ["atendimento", "desempenho", "inovação/reconhecimento"], "Imprensa elogia redução de 60% nas filas presenciais após implantação do portal.", False),
        (sys1.id, "seed", "x", "Consegui agendar minha consulta sem sair de casa no Cidadao360!", "Finalmente um sistema da prefeitura que funciona rápido no celular e explica tudo fácil.", "https://x.com/exemplo/status/1001", "@maria_cidada", "Cidadao360", now - timedelta(days=4), "positivo", 0.91, 0.95, ["usabilidade", "atendimento"], "Cidadã elogia facilidade de agendamento pelo celular.", False),
        (sys1.id, "seed", "reclame_aqui", "Erro no login gov.br ao anexar comprovante de residência", "Tentei enviar o PDF três vezes hoje de manhã e o sistema ficou carregando infinito no Safari.", "https://reclameaqui.exemplo.com.br/cidadao360/992", "João P.", "Portal Cidadão Digital 360", now - timedelta(days=3), "negativo", -0.68, 0.89, ["bug/estabilidade", "usabilidade"], "Usuário relata travamento no upload de PDF após login gov.br no Safari.", False),
        (sys1.id, "seed", "instagram", "Alguém sabe se o agendamento de IPTU já abriu no Cidadao360?", "Vi o anúncio mas ainda não achei o menu para parcelamento.", "https://instagram.com/p/exemplo2026", "@carlos_oliveira", "#Cidadao360", now - timedelta(days=2), "neutro", 0.05, 0.81, ["usabilidade", "atendimento"], "Dúvida sobre localização do menu de parcelamento de IPTU.", False),
        (sys1.id, "seed", "reddit", "Portal fora do ar agora de tarde? Precisava emitir guia urgente", "Erro 503 aparecendo faz 40 minutos no portal cidadao360, várias pessoas reclamando.", "https://reddit.com/r/brasil/comments/exemplo", "u/dev_cidadao", "Cidadao360", now - timedelta(days=1), "negativo", -0.86, 0.94, ["desempenho", "bug/estabilidade"], "Sinal de indisponibilidade (erro 503) relatado por usuários na emissão de guias.", True),
        (sys1.id, "seed", "youtube", "Tutorial: como usar o novo assistente de voz do Cidadão 360 para idosos", "Excelente iniciativa de acessibilidade, minha mãe conseguiu consultar o benefício sozinha.", "https://youtube.com/watch?v=exemplo360", "Canal Cidadania Digital", "Portal Cidadão Digital 360", now - timedelta(hours=14), "positivo", 0.88, 0.93, ["acessibilidade", "inovação/reconhecimento"], "Vídeo tutorial elogia acessibilidade por voz para idosos.", False),
        (sys2.id, "seed", "news", "Iniciativa FilaZero Saúde inicia piloto em 12 unidades básicas", "Projeto sem custos de licença aposta em transparência simples para mostrar posição real na fila.", "https://saude.exemplo.org.br/filazero-piloto", "Jornal Saúde Pública", "FilaZero Saúde", now - timedelta(days=2), "positivo", 0.76, 0.88, ["inovação/reconhecimento", "atendimento"], "Cobertura positiva do início do piloto de transparência de filas nas UBS.", False),
    ]

    for row in sample_mentions:
        (
            sid, conn, plat, title, content, url, author, kw, pub_dt,
            sent, score, conf, topics, summary, crisis
        ) = row
        chash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        db.add(
            Mention(
                system_id=sid,
                content_hash=chash,
                source_connector=conn,
                platform=plat,
                title=title,
                content=content,
                url=url,
                author=author,
                matched_keyword=kw,
                published_at=pub_dt,
                sentiment=sent,
                sentiment_score=score,
                confidence=conf,
                topics_json=json.dumps(topics, ensure_ascii=False),
                summary=summary,
                is_crisis_signal=crisis,
                analyzed_by="seed_demo",
                collected_at=pub_dt,
            )
        )

    # Seed top matching global awards from curated catalog for both starter systems
    for system in (sys1, sys2):
        scored = []
        for award in CURATED_GLOBAL_AWARDS:
            score, reasoning, next_steps = _score_curated_award(system, award)
            if score >= 62:
                scored.append((score, reasoning, next_steps, award))
        scored.sort(key=lambda x: x[0], reverse=True)
        for score, reasoning, next_steps, award in scored[:6]:
            annual = award.get("annual_deadline")
            iso_deadline = next_annual_date(annual[0], annual[1], min_days_ahead=15) if annual else ""
            db.add(
                AwardOpportunity(
                    system_id=system.id,
                    fingerprint=_award_fingerprint(award["title"], award["organizer"]),
                    title=award["title"],
                    organizer=award["organizer"],
                    description=award["description"],
                    official_url=award["official_url"],
                    scope=award["scope"],
                    country_region=award["country_region"],
                    country=award["country"],
                    city=award["city"],
                    latitude=award["latitude"],
                    longitude=award["longitude"],
                    ai_requirement=award["ai_requirement"],
                    stage_eligibility=award["stage_eligibility"],
                    deadline=award["deadline"],
                    deadline_date=iso_deadline,
                    award_status=award["award_status"],
                    prize_benefits=award["prize_benefits"],
                    categories_json=json.dumps(award["categories"], ensure_ascii=False),
                    match_score=score,
                    match_reasoning=reasoning,
                    next_steps=next_steps,
                    discovery_source="curated_catalog",
                    pipeline_status="novo",
                    user_notes="",
                )
            )

    db.commit()
