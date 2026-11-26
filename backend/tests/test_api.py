from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Use isolated temp SQLite database for tests
_tmp_dir = tempfile.mkdtemp(prefix="cidadao_pulse_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_tmp_dir) / 'test.db').as_posix()}"
os.environ["GEMINI_API_KEY"] = ""

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_seed(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    systems = client.get("/api/systems").json()
    assert len(systems) >= 2


def test_system_crud_and_awards_radar(client: TestClient):
    payload = {
        "name": "Transparência Obra Cidadã",
        "description": "Sistema sem IA que permite ao cidadão acompanhar obras públicas municipais com fotos e orçamento aberto.",
        "urls": ["https://obrascidada.exemplo.gov.br"],
        "keywords": ["Obra Cidadã", "transparência obras"],
        "stage": "iniciativa",
        "uses_ai": "sem_ia",
        "ai_details": "",
        "citizen_area": "Transparência",
        "target_audience": "Cidadãos e conselhos comunitários",
        "organization_type": "Governo Municipal",
        "country": "Brasil",
        "impact_summary": "Aumento do controle social sobre obras locais.",
        "monitor_sentiment": True,
        "monitor_awards": True,
        "is_active": True,
    }
    created = client.post("/api/systems", json=payload)
    assert created.status_code == 201
    sys_id = created.json()["id"]

    # Run global awards radar for this non-AI initiative system
    scan = client.post(
        "/api/awards/scan",
        json={"system_id": sys_id, "focus_scope": "todos", "include_ai_filter": "auto"},
    )
    assert scan.status_code == 200
    assert scan.json()["status"] == "completed"
    assert scan.json()["new_items"] > 0

    awards = client.get(f"/api/awards?system_id={sys_id}").json()
    assert len(awards) > 0
    # Verify non-AI system does not get AI-only award as top recommendation
    assert awards[0]["ai_requirement"] in {"ambos", "sem_ia"}

    # Update award pipeline status
    award_id = awards[0]["id"]
    patched = client.patch(
        f"/api/awards/{award_id}",
        json={"pipeline_status": "analisando", "user_notes": "Preparar documentação"},
    )
    assert patched.status_code == 200
    assert patched.json()["pipeline_status"] == "analisando"

    # Export Markdown & CSV reports
    md = client.get(f"/api/awards/export/report?format=markdown&system_id={sys_id}")
    assert md.status_code == 200
    assert "Radar Mundial de Premiações" in md.text

    csv_resp = client.get(f"/api/awards/export/report?format=csv&system_id={sys_id}")
    assert csv_resp.status_code == 200
    assert "Prêmio/Concurso" in csv_resp.text

    # Delete test system
    deleted = client.delete(f"/api/systems/{sys_id}")
    assert deleted.status_code == 204


def test_sentiment_overview_and_settings(client: TestClient):
    ov = client.get("/api/sentiment/overview")
    assert ov.status_code == 200
    data = ov.json()
    assert data["total_mentions"] > 0
    assert 0 <= data["sentiment_index"] <= 100

    connectors = client.get("/api/settings/connectors").json()
    ids = {c["id"] for c in connectors}
    assert {"gemini_web", "google_news", "reddit", "youtube", "apify_social", "x_api", "meta_api"} <= ids

    # Update schedule dynamically
    upd = client.put(
        "/api/settings",
        json={"awards_cron_day": "wed", "awards_cron_hour": 9, "sentiment_interval_hours": 6},
    )
    assert upd.status_code == 200
    assert upd.json()["awards_cron_day"] == "wed"
    assert upd.json()["next_awards_run"] is not None


def test_relevance_filter_blocks_false_positives_for_ded_plus():
    import json
    from types import SimpleNamespace
    from app.services.relevance import build_contextual_search_queries, evaluate_mention_relevance

    ded_system = SimpleNamespace(
        name="DED+ (Diário Escolar Digital)",
        description=(
            "O DED+ (Diário Escolar Digital+) é um sistema informatizado da Secretaria de Estado "
            "de Educação de Minas Gerais (SEE/MG), desenvolvido em parceria com a Prodemge, "
            "destinado ao registro de frequência e notas dos estudantes da rede estadual."
        ),
        urls_json=json.dumps([
            "https://dedmais.educacao.mg.gov.br/",
            "https://www.diarioescolardigital.educacao.mg.gov.br/site/",
            "https://www.agenciaminas.mg.gov.br/",
        ]),
        keywords_json=json.dumps([
            "DED+", "DED Mais", "Diário Escolar Digital", "SEE MG", "Prodemge"
        ]),
        citizen_area="Educação",
        organization_type="Governo Estadual",
        target_audience="Professores e estudantes da rede estadual de MG",
    )

    # Queries should anchor short terms like DED+ / DED Mais with context
    queries = build_contextual_search_queries(ded_system)
    assert any("Educação" in q or "Minas Gerais" in q for q, _ in queries)

    # Irrelevant articles MUST be rejected
    futsal_ok, _, _ = evaluate_mention_relevance(
        ded_system,
        title="FOTOS: Em dia de luto, ABC elimina Macau e faz final do Potiguar de Futsal - ge",
        content="Em partida emocionante pelo campeonato Potiguar de Futsal, ABC garante vaga na final.",
        url="https://ge.globo.com/rn/noticia/2016/11/fotos-em-dia-de-luto-abc-elimina-macau-e-faz-final-do-potiguar-de-futsal.html",
        matched_keyword="DED Mais",
    )
    assert futsal_ok is False

    f1_ok, _, _ = evaluate_mention_relevance(
        ded_system,
        title="F1: Qual é o segredo por trás do sistema de direção da Mercedes? - Motorsport.com",
        content="A Mercedes apresentou inovação aerodinâmica e no volante durante os testes de Fórmula 1.",
        url="https://motorsport.uol.com.br/f1/news/mercedes",
        matched_keyword="DED Mais",
    )
    assert f1_ok is False

    # Genuine DED+ / Diário Escolar Digital articles MUST pass
    ded_video_ok, score1, _ = evaluate_mention_relevance(
        ded_system,
        title="DED+ é apresentado em videocast do Centro de Inovação para Educação Brasileira - Consed",
        content="O sistema DED+ de Minas Gerais foi destaque no videocast sobre inovação educacional.",
        url="https://consed.org.br/noticia/ded-mais",
        matched_keyword="DED+",
    )
    assert ded_video_ok is True
    assert score1 >= 0.7

    diario_ok, score2, _ = evaluate_mention_relevance(
        ded_system,
        title="Novas funções no Diário Escolar Digital ampliam apoio à gestão e ao trabalho dos educadores em Minas Gerais",
        content="Secretaria de Educação de MG lança melhorias no Diário Escolar Digital para professores.",
        url="https://agenciaminas.mg.gov.br/noticia/diario-escolar",
        matched_keyword="Diário Escolar Digital",
    )
    assert diario_ok is True
    assert score2 >= 0.85


def test_temporal_analysis_windows(client: TestClient):
    for days, expected_granularity, expected_buckets in [
        (7, "day", 7),
        (14, "day", 14),
        (30, "day", 30),
        (180, "month", 6),
        (365, "month", 12),
    ]:
        resp = client.get(f"/api/sentiment/temporal?days={days}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == days
        assert data["granularity"] == expected_granularity
        assert len(data["series"]) == expected_buckets
        assert [w["days"] for w in data["windows_summary"]] == [7, 14, 30, 180, 365]
        assert {g["group"] for g in data["channel_groups"]} == {"redes_sociais", "internet"}
        assert data["narrative_summary"]


def test_geographic_scope_anchors_queries_and_blocks_other_states(client: TestClient):
    import json
    from types import SimpleNamespace
    from app.services.relevance import build_contextual_search_queries, evaluate_mention_relevance

    # Create municipal/state system via API and verify persistence of state_uf & municipality
    created = client.post(
        "/api/systems",
        json={
            "name": "Diário Escolar Digital",
            "description": "Sistema estadual de acompanhamento escolar.",
            "urls": ["https://dedmais.educacao.mg.gov.br/"],
            "keywords": ["DED+", "Diário Escolar Digital"],
            "stage": "producao",
            "uses_ai": "com_ia",
            "citizen_area": "Educação",
            "organization_type": "Governo Estadual",
            "country": "Brasil",
            "state_uf": "mg",
            "municipality": "",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["state_uf"] == "MG"
    client.delete(f"/api/systems/{body['id']}")

    mg_system = SimpleNamespace(
        name="DED+ (Diário Escolar Digital)",
        description="Sistema da SEE/MG para professores e estudantes.",
        urls_json=json.dumps(["https://dedmais.educacao.mg.gov.br/"]),
        keywords_json=json.dumps(["DED+", "Diário Escolar Digital"]),
        citizen_area="Educação",
        organization_type="Governo Estadual",
        target_audience="Professores e estudantes",
        state_uf="MG",
        municipality="",
    )

    queries = build_contextual_search_queries(mg_system)
    assert any("Minas Gerais" in q and "MG" in q for q, _ in queries)

    # Article about a Diário Escolar Digital in ANOTHER state (Paraná) MUST be rejected!
    other_state_ok, _, reason = evaluate_mention_relevance(
        mg_system,
        title="Governo do Paraná lança novo Diário Escolar Digital para rede paranaense",
        content="A Secretaria de Educação do Paraná anunciou atualização do sistema escolar.",
        url="https://www.aen.pr.gov.br/noticia/diario-escolar",
        matched_keyword="Diário Escolar Digital",
    )
    assert other_state_ok is False
    assert "Paraná" in reason

    # Article about Minas Gerais MUST pass!
    mg_ok, score, _ = evaluate_mention_relevance(
        mg_system,
        title="Minas Gerais amplia recursos do Diário Escolar Digital para professores",
        content="Educadores da rede estadual mineira já podem acessar as novidades do DED+.",
        url="https://agenciaminas.mg.gov.br/noticia/ded",
        matched_keyword="Diário Escolar Digital",
    )
    assert mg_ok is True
    assert score >= 0.9

    # Ensure Portuguese preposition "para" NEVER falsely triggers Pará state conflict!
    preposition_ok, _, _ = evaluate_mention_relevance(
        mg_system,
        title="Diário Escolar Digital+ já está disponível para os professores da rede estadual",
        content="Novo módulo para lançamento de frequência e notas dos estudantes.",
        url="https://consed.org.br/noticia/ded-professores",
        matched_keyword="DED+",
    )
    assert preposition_ok is True


def test_import_instagram_comments_and_problem_diagnostics(client: TestClient):
    systems = client.get("/api/systems").json()
    sys_id = systems[0]["id"]

    # Import realistic Instagram comments (mix of login errors, outage, mobile usability, praise)
    raw_comments = "\n".join([
        "@prof_ana | Não consigo entrar, dá erro no login e senha bloqueada o tempo todo!",
        "@marcos_bh | Sistema fora do ar desde ontem com erro 503 no fechamento do bimestre!",
        "@carla_mg | Muito lento e travando no celular, demora demais para carregar as turmas.",
        "@joao_prof | Onde fica o botão para baixar o relatório de frequência? Alguém sabe?",
        "@lucia_ed | Adorei a nova versão, ficou excelente e bem mais rápida para mim.",
    ])

    imp = client.post(
        "/api/sentiment/import-comments",
        json={
            "system_id": sys_id,
            "platform": "instagram",
            "post_url": "https://www.instagram.com/p/exemplo-ded-2026/",
            "raw_text": raw_comments,
        },
    )
    assert imp.status_code == 200
    imp_data = imp.json()
    assert imp_data["parsed"] == 5
    assert imp_data["saved"] == 5

    # Run problem diagnostics filtered specifically to Instagram & Facebook
    diag = client.get(f"/api/sentiment/problems?system_id={sys_id}&channel_group=instagram_facebook&days=30")
    assert diag.status_code == 200
    d = diag.json()
    assert d["total_comments_analyzed"] >= 5
    assert d["total_friction_mentions"] >= 4
    assert d["problems_count"] >= 3
    assert d["top_complaint_channel"] == "instagram"
    assert d["executive_summary"]
    # Verify each problem cluster includes real evidences with direct URL
    first_prob = d["problems"][0]
    assert first_prob["recommended_action"]
    assert len(first_prob["evidences"]) >= 1
    assert first_prob["evidences"][0]["url"] == "https://www.instagram.com/p/exemplo-ded-2026/"


def test_awards_15_day_deadline_filter_and_geolocation(client: TestClient):
    from datetime import date, timedelta
    from app.database import SessionLocal
    from app.models import AwardOpportunity

    systems = client.get("/api/systems").json()
    sys_id = systems[0]["id"]

    # Insert one expired award, one urgent (<15d) award, and one eligible (>=15d) award
    db = SessionLocal()
    try:
        today = date.today()
        db.add_all([
            AwardOpportunity(
                system_id=sys_id,
                fingerprint="fp-expired-test",
                title="Prêmio Já Encerrado",
                organizer="Org Passada",
                country_region="Brasil",
                country="Brasil",
                city="Brasília",
                latitude=-15.79,
                longitude=-47.88,
                deadline="Encerrado",
                deadline_date=(today - timedelta(days=5)).isoformat(),
                award_status="aberto",
                match_score=95,
            ),
            AwardOpportunity(
                system_id=sys_id,
                fingerprint="fp-too-soon-test",
                title="Prêmio Fecha em 7 Dias",
                organizer="Org Curta",
                country_region="Espanha",
                country="Espanha",
                city="Barcelona",
                latitude=41.38,
                longitude=2.17,
                deadline="Fecha em breve",
                deadline_date=(today + timedelta(days=7)).isoformat(),
                award_status="aberto",
                match_score=94,
            ),
            AwardOpportunity(
                system_id=sys_id,
                fingerprint="fp-eligible-30d-test",
                title="Prêmio Aberto 30 Dias",
                organizer="Org Global",
                country_region="Suíça",
                country="Suíça",
                city="Genebra",
                latitude=46.2044,
                longitude=6.1432,
                deadline="Aberto",
                deadline_date=(today + timedelta(days=30)).isoformat(),
                award_status="aberto",
                match_score=93,
            ),
        ])
        db.commit()
    finally:
        db.close()

    # Default GET /api/awards enforces min_days_ahead=15 and hides expired & <15d awards!
    open_awards = client.get(f"/api/awards?system_id={sys_id}").json()
    titles = {a["title"] for a in open_awards}
    assert "Prêmio Já Encerrado" not in titles
    assert "Prêmio Fecha em 7 Dias" not in titles
    assert "Prêmio Aberto 30 Dias" in titles

    target = next(a for a in open_awards if a["title"] == "Prêmio Aberto 30 Dias")
    assert target["days_remaining"] == 30
    assert target["country"] == "Suíça"
    assert target["city"] == "Genebra"
    assert target["latitude"] is not None and target["longitude"] is not None

    # Marking an award as closed MUST NOT be overwritten when re-running the awards scan!
    closed_patch = client.patch(
        f"/api/awards/{target['id']}",
        json={"award_status": "encerrado", "deadline_source_note": "Marcado como encerrado pelo usuário."},
    )
    assert closed_patch.status_code == 200
    rescan = client.post("/api/awards/scan", json={"system_id": sys_id, "focus_scope": "todos"})
    assert rescan.status_code == 200
    after_titles = {a["title"] for a in client.get(f"/api/awards?system_id={sys_id}").json()}
    assert "Prêmio Aberto 30 Dias" not in after_titles


def test_mention_quality_rejects_corrupted_snippets_sidebar_leaks_and_spam():
    import json
    from types import SimpleNamespace
    from app.services.relevance import evaluate_mention_quality

    ded = SimpleNamespace(
        name="DED+ (Diário Escolar Digital)",
        description="Sistema da SEE/MG para professores e estudantes.",
        urls_json=json.dumps(["https://dedmais.educacao.mg.gov.br/"]),
        keywords_json=json.dumps(["DED+", "Diário Escolar Digital", "DED IA"]),
        citizen_area="Educação",
        organization_type="Governo Estadual",
        target_audience="Professores",
        state_uf="MG",
        municipality="",
    )

    # 1. Corrupted multi-result concatenated DDGS Facebook soup MUST be rejected
    ok1, _ = evaluate_mention_quality(
        source_connector="open_web_social",
        platform="facebook",
        content_type="post",
        title="Diário de Notícias Minas - FacebookContratação Temporária - SEE MG ...PERÍODO DE TAXAÇÃO SEE/MG 2026 - Facebook",
        content="Nov 2, 2026 · DED IA chega... Feb 3, 2026 · *DED IA chega...",
        url="https://www.facebook.com/diariodenoticiasminas/",
        system=ded,
    )
    assert ok1 is False

    # 2. Facebook sidebar leak (URL & title about Teófilo Otoni, unrelated sidebar snippet mentioning DED IA) MUST be rejected
    ok2, _ = evaluate_mention_quality(
        source_connector="open_web_social",
        platform="facebook",
        content_type="post",
        title="Mais... - Secretaria de Educação de Minas Gerais | Facebook",
        content="Nov 10, 2026 · Professor, o Governo de Minas acaba de lançar o DED IA no Diário Escolar Digital (DED+)!",
        url="https://www.facebook.com/secretariadeeducacaomg/posts/mais-investimentos-e-melhorias-em-teofilo-otoni/1585654910259268/",
        system=ded,
    )
    assert ok2 is False

    # 3. Corrupted concatenated YouTube search result MUST be rejected
    ok3, _ = evaluate_mention_quality(
        source_connector="open_web_social",
        platform="youtube",
        content_type="post",
        title="NOVO DIÁRIO DIGITAL ESCOLAR 2024 ...How to close the semester in DED+ MG",
        content="Feb 27, 2024 · Tutorial... Apr 17, 2024 · How to close...",
        url="https://www.youtube.com/watch?v=qNIT3bK4Uuc",
        system=ded,
    )
    assert ok3 is False

    # 4. Clean single YouTube video with direct watch URL MUST pass
    ok4, _ = evaluate_mention_quality(
        source_connector="open_web_social",
        platform="youtube",
        content_type="post",
        title="Como acessar o Aprender Já MG na plataforma Plurall pelo seu DED+",
        content="Mar 26, 2026 · Passo a passo para entrar na plataforma pelo seu DED+.",
        url="https://www.youtube.com/watch?v=U1w5_4GunBM",
        system=ded,
    )
    assert ok4 is True

    # 5. Engagement-bait spam comment on Apify MUST be rejected, while real user comment MUST pass
    ok5, _ = evaluate_mention_quality(
        source_connector="apify_social",
        platform="instagram",
        content_type="comment",
        title="Comentário de bonjesuense",
        content="Aumente o seu engajamento! Marque 5 amigos nos comentários. Conheça nossos parceiros!",
        url="https://www.instagram.com/p/DfkWaG3PRPA/c/123",
        system=ded,
    )
    assert ok5 is False

    ok6, _ = evaluate_mention_quality(
        source_connector="apify_social",
        platform="instagram",
        content_type="comment",
        title="Comentário de gabi1409",
        content="Gostei demais do DED IA! Desenvolvido pelos servidores da SEEMG!",
        url="https://www.instagram.com/p/DfkWaG3PRPA/c/456",
        system=ded,
    )
    assert ok6 is True

    # 6. Off-topic government/salary hijacking comments and empty/emoji reactions MUST be rejected
    for off_topic_text in [
        "Gostaria de aproveitar para questionar sobre o pagamento do piso salarial aos professores. Existe um fundo específico para isso. Não tem razão para não pagar.",
        "E as condições de salário? Saneamento básico? Condições para alunos TEA ? Isso é uma piada de pessimo gosto!",
        "Sério ?",
        "É pra rir?",
        "👏👏👏👏",
    ]:
        ok_off, _ = evaluate_mention_quality(
            source_connector="apify_social",
            platform="instagram",
            content_type="comment",
            title="Comentário off-topic",
            content=off_topic_text,
            url="https://www.instagram.com/p/DfkWaG3PRPA/c/999",
            system=ded,
        )
        assert ok_off is False, f"Expected off-topic comment to be rejected: {off_topic_text}"

    # 7. Genuine product/tool feedback comments MUST pass even without repeating the full system name
    for valid_comment in [
        "Toda ferramenta que for para ajudar na execução do trabalho é bem vinda",
        "o DED é bom mas precisa de melhorias !! Porque não investir primeiro em melhorar aplicativo?",
        "Como tudo que vem da SEE e da Prodemge, não funciona!!!",
    ]:
        ok_valid, _ = evaluate_mention_quality(
            source_connector="apify_social",
            platform="instagram",
            content_type="comment",
            title="Comentário válido",
            content=valid_comment,
            url="https://www.instagram.com/p/DfkWaG3PRPA/c/888",
            system=ded,
        )
        assert ok_valid is True, f"Expected valid comment to pass: {valid_comment}"


def test_database_url_normalization_and_optional_password_auth(client: TestClient, monkeypatch):
    from app.database import normalize_database_url

    assert normalize_database_url("postgres://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("postgresql://u:p@host/db?sslmode=require") == (
        "postgresql+psycopg://u:p@host/db?sslmode=require"
    )
    assert normalize_database_url("sqlite:///data.db") == "sqlite:///data.db"

    # Without APP_PASSWORD, auth is disabled (defaults to Admin Local)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    st_open = client.get("/api/auth/status").json()
    assert st_open["auth_required"] is False
    assert st_open["authenticated"] is True
    assert st_open["role"] == "admin"

    # With APP_PASSWORD enabled, API endpoints require login token
    monkeypatch.setenv("APP_PASSWORD", "super-secret-2026")
    st_locked = client.get("/api/auth/status").json()
    assert st_locked["auth_required"] is True
    assert st_locked["authenticated"] is False

    # Health check remains public; /api/systems returns 401 without token
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/systems").status_code == 401

    # Wrong password rejected
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401

    # Right admin password returns valid admin session token
    login_resp = client.post("/api/auth/login", json={"password": "super-secret-2026"})
    assert login_resp.status_code == 200
    admin_token = login_resp.json()["token"]
    assert admin_token
    assert login_resp.json()["role"] == "admin"

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    assert client.get("/api/systems", headers=admin_headers).status_code == 200
    assert client.get("/api/systems", headers={"X-App-Password": "super-secret-2026"}).status_code == 200

    # Admin creates a read-only ("viewer") guest token with a friendly custom word
    create_viewer = client.post(
        "/api/auth/tokens",
        json={
            "label": "Diretoria SEE-MG",
            "role": "viewer",
            "expires_in_days": 30,
            "custom_token": "educacao2026",
        },
        headers=admin_headers,
    )
    assert create_viewer.status_code == 201
    viewer_data = create_viewer.json()
    viewer_raw_token = viewer_data["token"]
    assert viewer_raw_token == "educacao2026"

    # Also verify auto-generated friendly token format (word-1234)
    auto_tok = client.post(
        "/api/auth/tokens",
        json={"label": "Equipe Auto", "role": "viewer", "expires_in_days": 7},
        headers=admin_headers,
    )
    assert auto_tok.status_code == 201
    assert "-" in auto_tok.json()["token"]
    client.delete(f"/api/auth/tokens/{auto_tok.json()['id']}", headers=admin_headers)

    # Guest logs in using the cp_ token
    guest_login = client.post("/api/auth/login", json={"password": viewer_raw_token})
    assert guest_login.status_code == 200
    assert guest_login.json()["role"] == "viewer"
    assert guest_login.json()["label"] == "Diretoria SEE-MG"

    viewer_headers = {"Authorization": f"Bearer {viewer_raw_token}"}
    # Viewer CAN read dashboards/systems/awards, CANNOT mutate or access settings/tokens
    assert client.get("/api/systems", headers=viewer_headers).status_code == 200
    assert client.get("/api/awards", headers=viewer_headers).status_code == 200
    assert client.get("/api/settings", headers=viewer_headers).status_code == 403
    assert client.get("/api/auth/tokens", headers=viewer_headers).status_code == 403
    assert client.post("/api/systems", json={"name": "Hack"}, headers=viewer_headers).status_code == 403

    # Admin revokes the viewer token -> immediately loses access (401)
    assert client.delete(f"/api/auth/tokens/{viewer_data['id']}", headers=admin_headers).status_code == 204
    assert client.get("/api/systems", headers=viewer_headers).status_code == 401

    # Admin configures Google (Gmail) Login via access-config endpoint
    upd = client.put(
        "/api/auth/access-config",
        json={
            "google_client_id": "test-client-id.apps.googleusercontent.com",
            "admin_google_emails": "admin@gmail.com",
            "allowed_google_emails": "gestor@gmail.com",
        },
        headers=admin_headers,
    )
    assert upd.status_code == 200
    assert client.get("/api/auth/status").json()["google_enabled"] is True

    # Mock Google ID token verification for admin, guest, and unauthorized email
    import app.main as main_mod

    async def fake_verify(cred: str, cid: str):
        return {"email": cred, "email_verified": "true", "aud": cid}

    monkeypatch.setattr(main_mod, "_verify_google_id_token", fake_verify)

    g_admin = client.post("/api/auth/google", json={"credential": "admin@gmail.com"})
    assert g_admin.status_code == 200
    assert g_admin.json()["role"] == "admin"
    assert client.get("/api/settings", headers={"Authorization": f"Bearer {g_admin.json()['token']}"}).status_code == 200

    g_guest = client.post("/api/auth/google", json={"credential": "gestor@gmail.com"})
    assert g_guest.status_code == 200
    assert g_guest.json()["role"] == "viewer"
    assert client.get("/api/systems", headers={"Authorization": f"Bearer {g_guest.json()['token']}"}).status_code == 200
    assert client.get("/api/settings", headers={"Authorization": f"Bearer {g_guest.json()['token']}"}).status_code == 403

    g_denied = client.post("/api/auth/google", json={"credential": "estranho@gmail.com"})
    assert g_denied.status_code == 403

    # Even without APP_PASSWORD, having admin_google_emails set strictly enforces login (no local bypass!)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert client.get("/api/auth/status").json()["auth_required"] is True
    assert client.get("/api/systems").status_code == 401

    # Re-authenticate via Google (now signed without APP_PASSWORD) and clean up auth settings
    g_admin2 = client.post("/api/auth/google", json={"credential": "admin@gmail.com"})
    assert g_admin2.status_code == 200
    assert (
        client.put(
            "/api/auth/access-config",
            json={"clear_app_password": True, "google_client_id": "", "admin_google_emails": "", "allowed_google_emails": ""},
            headers={"Authorization": f"Bearer {g_admin2.json()['token']}"},
        ).status_code
        == 200
    )


def test_project_star_ratings_endpoint(client: TestClient):
    resp = client.get("/api/sentiment/star-ratings?use_ai=false")
    assert resp.status_code == 200
    ratings = resp.json()
    assert len(ratings) >= 1
    first = ratings[0]
    assert 0.0 <= first["stars"] <= 5.0
    assert first["rating_label"]
    assert first["rating_reason"]
    assert [b["stars"] for b in first["star_distribution"]] == [5, 4, 3, 2, 1]
    assert sum(b["count"] for b in first["star_distribution"]) == first["total_mentions"]










