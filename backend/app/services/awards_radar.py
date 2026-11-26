from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session

from app.models import AwardOpportunity, MonitoredSystem
from app.services.gemini_client import call_gemini_interaction, extract_json_payload
from app.services.relevance import strip_html

logger = logging.getLogger(__name__)


# ============================================================
# Geocoding lookup for global GovTech / CivicTech cities & countries
# ============================================================
KNOWN_LOCATIONS: dict[str, tuple[str, str, float, float]] = {
    # keyword -> (country, city, lat, lng)
    "brasília": ("Brasil", "Brasília", -15.7939, -47.8828),
    "brasilia": ("Brasil", "Brasília", -15.7939, -47.8828),
    "são paulo": ("Brasil", "São Paulo", -23.5505, -46.6333),
    "sao paulo": ("Brasil", "São Paulo", -23.5505, -46.6333),
    "belo horizonte": ("Brasil", "Belo Horizonte", -19.9167, -43.9345),
    "rio de janeiro": ("Brasil", "Rio de Janeiro", -22.9068, -43.1729),
    "curitiba": ("Brasil", "Curitiba", -25.4284, -49.2733),
    "brasil": ("Brasil", "Brasília", -15.7939, -47.8828),
    "brazil": ("Brasil", "Brasília", -15.7939, -47.8828),
    "genebra": ("Suíça", "Genebra", 46.2044, 6.1432),
    "geneva": ("Suíça", "Genebra", 46.2044, 6.1432),
    "suíça": ("Suíça", "Genebra", 46.2044, 6.1432),
    "switzerland": ("Suíça", "Genebra", 46.2044, 6.1432),
    "dubai": ("Emirados Árabes Unidos", "Dubai", 25.2048, 55.2708),
    "eau": ("Emirados Árabes Unidos", "Dubai", 25.2048, 55.2708),
    "uae": ("Emirados Árabes Unidos", "Dubai", 25.2048, 55.2708),
    "barcelona": ("Espanha", "Barcelona", 41.3851, 2.1734),
    "espanha": ("Espanha", "Barcelona", 41.3851, 2.1734),
    "spain": ("Espanha", "Barcelona", 41.3851, 2.1734),
    "nova york": ("Estados Unidos", "Nova York", 40.7489, -73.9680),
    "new york": ("Estados Unidos", "Nova York", 40.7489, -73.9680),
    "washington": ("Estados Unidos", "Washington, D.C.", 38.9072, -77.0369),
    "cambridge": ("Estados Unidos", "Cambridge (Boston)", 42.3601, -71.0942),
    "boston": ("Estados Unidos", "Boston", 42.3601, -71.0589),
    "eua": ("Estados Unidos", "Nova York", 40.7489, -73.9680),
    "usa": ("Estados Unidos", "Washington, D.C.", 38.9072, -77.0369),
    "paris": ("França", "Paris", 48.8566, 2.3522),
    "frança": ("França", "Paris", 48.8566, 2.3522),
    "france": ("França", "Paris", 48.8566, 2.3522),
    "oslo": ("Noruega", "Oslo", 59.9139, 10.7522),
    "noruega": ("Noruega", "Oslo", 59.9139, 10.7522),
    "londres": ("Reino Unido", "Londres", 51.5074, -0.1278),
    "london": ("Reino Unido", "Londres", 51.5074, -0.1278),
    "reino unido": ("Reino Unido", "Londres", 51.5074, -0.1278),
    "guayaquil": ("Equador", "Guayaquil", -2.1894, -79.8891),
    "américa latina": ("Equador", "Guayaquil", -2.1894, -79.8891),
    "latam": ("Equador", "Guayaquil", -2.1894, -79.8891),
    "bruxelas": ("Bélgica", "Bruxelas", 50.8503, 4.3517),
    "brussels": ("Bélgica", "Bruxelas", 50.8503, 4.3517),
    "singapura": ("Singapura", "Singapura", 1.3521, 103.8198),
    "singapore": ("Singapura", "Singapura", 1.3521, 103.8198),
    "estônia": ("Estônia", "Tallinn", 59.4370, 24.7536),
    "tallinn": ("Estônia", "Tallinn", 59.4370, 24.7536),
    "lisboa": ("Portugal", "Lisboa", 38.7223, -9.1393),
    "portugal": ("Portugal", "Lisboa", 38.7223, -9.1393),
    "tóquio": ("Japão", "Tóquio", 35.6762, 139.6503),
    "seul": ("Coreia do Sul", "Seul", 37.5665, 126.9780),
    "berlim": ("Alemanha", "Berlim", 52.5200, 13.4050),
    "global": ("Suíça", "Genebra", 46.2044, 6.1432),
}


def next_annual_date(month: int, day: int, min_days_ahead: int = 15) -> str:
    """Return the next upcoming YYYY-MM-DD for a recurring annual deadline with at least min_days_ahead."""
    today = date.today()
    candidate = date(today.year, month, day)
    if (candidate - today).days < min_days_ahead:
        candidate = date(today.year + 1, month, day)
    return candidate.isoformat()


def parse_deadline_date(raw_date: str | None) -> date | None:
    if not raw_date:
        return None
    cleaned = str(raw_date).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", cleaned)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m_br = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", cleaned)
    if m_br:
        try:
            return date(int(m_br.group(3)), int(m_br.group(2)), int(m_br.group(1)))
        except ValueError:
            return None
    return None


def compute_days_remaining(deadline_date_str: str | None) -> int | None:
    d = parse_deadline_date(deadline_date_str)
    if d is None:
        return None
    return (d - date.today()).days


def is_award_open_with_buffer(
    award_status: str,
    deadline_date_str: str | None,
    min_days_ahead: int = 15,
    include_upcoming_cycles: bool = False,
) -> tuple[bool, int | None]:
    """
    Returns (is_open_for_application, days_remaining).
    Strict default (include_upcoming_cycles=False):
      - ONLY 'aberto' awards with (rolling/no fixed end date OR days_remaining >= min_days_ahead) return True!
      - 'encerrado', 'previsto', and unverified 'recorrente' return False by default so closed awards never appear as open.
    When include_upcoming_cycles=True:
      - Also allows 'previsto' and 'recorrente' (still blocking 'encerrado' and past dates).
    """
    status = (award_status or "").lower()
    days_rem = compute_days_remaining(deadline_date_str)
    if status == "encerrado":
        return False, days_rem
    if days_rem is not None and days_rem < min_days_ahead:
        return False, days_rem
    if status == "aberto":
        return True, days_rem
    if include_upcoming_cycles and status in {"previsto", "recorrente"}:
        return True, days_rem
    return False, days_rem


def resolve_award_geolocation(
    country: str = "",
    city: str = "",
    country_region: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[str, str, float, float]:
    if latitude is not None and longitude is not None:
        return (country or country_region or "Global", city or country or "Global", float(latitude), float(longitude))
    hay = f"{city} {country} {country_region}".lower()
    for key, (c_name, city_name, lat, lng) in KNOWN_LOCATIONS.items():
        if key in hay:
            return (country or c_name, city or city_name, lat, lng)
    return (country or "Internacional", city or "Genebra", 46.2044, 6.1432)


# ============================================================
# Catálogo Global e Brasileiro Curado de Premiações e Concursos
# com País, Cidade, Coordenadas e Próxima Janela de Inscrição
# ============================================================
CURATED_GLOBAL_AWARDS: list[dict[str, Any]] = [
    {
        "title": "UN Public Service Awards (UNPSA)",
        "organizer": "Nações Unidas (UN DESA)",
        "description": "Principal reconhecimento internacional da ONU para excelência e inovação em serviços públicos digitais e atendimento inclusivo ao cidadão alinhados aos ODS.",
        "official_url": "https://publicadministration.un.org/unpsa/",
        "scope": "internacional",
        "country_region": "Estados Unidos (ONU)",
        "country": "Estados Unidos",
        "city": "Nova York",
        "latitude": 40.7489,
        "longitude": -73.9680,
        "ai_requirement": "ambos",
        "stage_eligibility": "producao",
        "deadline": "Próximo ciclo anual ONU (Inscrições até Março)",
        "annual_deadline": (3, 31),
        "award_status": "aberto",
        "prize_benefits": "Troféu internacional ONU, cerimônia global no Dia do Serviço Público da ONU e vitrine mundial de boas práticas.",
        "categories": ["Serviços Públicos Digitais", "Inclusão", "Transparência", "Saúde", "Educação", "Governo Digital"],
    },
    {
        "title": "WSIS Prizes (World Summit on the Information Society)",
        "organizer": "ITU / Nações Unidas",
        "description": "Premiação global para projetos de tecnologia e software que usam TICs para melhorar a vida dos cidadãos (e-Government, e-Health, e-Learning, e-Environment). Aceita iniciativas e soluções já implementadas, com ou sem IA.",
        "official_url": "https://www.itu.int/net4/wsis/stocktaking/Prizes",
        "scope": "internacional",
        "country_region": "Suíça (ITU / ONU)",
        "country": "Suíça",
        "city": "Genebra",
        "latitude": 46.2044,
        "longitude": 6.1432,
        "ai_requirement": "ambos",
        "stage_eligibility": "ambos",
        "deadline": "Submissões anuais até Fevereiro",
        "annual_deadline": (2, 15),
        "award_status": "aberto",
        "prize_benefits": "Reconhecimento oficial da ITU/ONU em Genebra, publicação no WSIS Stocktaking Report e visibilidade internacional.",
        "categories": ["Governo Digital", "Saúde", "Educação", "Acessibilidade", "Meio Ambiente", "Serviços Públicos Digitais"],
    },
    {
        "title": "Concurso Inovação no Setor Público (ENAP)",
        "organizer": "Escola Nacional de Administração Pública (ENAP)",
        "description": "Tradicional concurso brasileiro que premia iniciativas e sistemas inovadores no setor público federal, estadual e municipal que geram valor real e melhoram o atendimento ao cidadão.",
        "official_url": "https://inovacao.enap.gov.br/",
        "scope": "nacional",
        "country_region": "Brasil",
        "country": "Brasil",
        "city": "Brasília",
        "latitude": -15.7939,
        "longitude": -47.8828,
        "ai_requirement": "ambos",
        "stage_eligibility": "producao",
        "deadline": "Edital anual (1º semestre — até Maio)",
        "annual_deadline": (5, 30),
        "award_status": "aberto",
        "prize_benefits": "Troféu ENAP, selo de inovação pública, publicação no Repositório Institucional e divulgação nacional.",
        "categories": ["Serviços Públicos Digitais", "Governo Digital", "Saúde", "Educação", "Assistência Social", "Transparência"],
    },
    {
        "title": "Prêmio Conexão Inova",
        "organizer": "Rede Conexão Inovação Pública",
        "description": "Premia projetos, softwares e iniciativas inovadoras no setor público brasileiro — incluindo categorias específicas para ideias/iniciativas em desenvolvimento e projetos já implementados para o cidadão.",
        "official_url": "https://www.conexaoinovacaopublica.org/",
        "scope": "nacional",
        "country_region": "Brasil",
        "country": "Brasil",
        "city": "Belo Horizonte",
        "latitude": -19.9167,
        "longitude": -43.9345,
        "ai_requirement": "ambos",
        "stage_eligibility": "ambos",
        "deadline": "Edição anual Convergência (até Abril)",
        "annual_deadline": (4, 20),
        "award_status": "aberto",
        "prize_benefits": "Reconhecimento nacional pela comunidade de inovação pública, apresentação no evento Convergência e troféu.",
        "categories": ["Serviços Públicos Digitais", "Inovação Pública", "Governo Digital", "Transparência", "Atendimento ao Cidadão"],
    },
    {
        "title": "GovTech Prize — World Governments Summit",
        "organizer": "World Governments Summit / Emirates Government Service Excellence",
        "description": "Prêmio mundial voltado a soluções tecnológicas governamentais (especialmente serviços centrados no cidadão, IA aplicada ao setor público e transformação digital).",
        "official_url": "https://www.worldgovernmentssummit.org/",
        "scope": "internacional",
        "country_region": "Emirados Árabes Unidos",
        "country": "Emirados Árabes Unidos",
        "city": "Dubai",
        "latitude": 25.2048,
        "longitude": 55.2708,
        "ai_requirement": "ambos",
        "stage_eligibility": "ambos",
        "deadline": "Chamada anual até Dezembro",
        "annual_deadline": (12, 22),
        "award_status": "aberto",
        "prize_benefits": "Premiação internacional no World Governments Summit em Dubai e destaque junto a líderes globais de governo digital.",
        "categories": ["Governo Digital", "Inteligência Artificial", "Serviços Públicos Digitais", "Mobilidade", "Saúde"],
    },
    {
        "title": "AI for Good — Innovation Factory",
        "organizer": "ITU / Nações Unidas",
        "description": "Competição global para soluções de Inteligência Artificial com alto impacto social e atendimento a necessidades dos cidadãos e ODS. Aceita iniciativas em desenvolvimento e sistemas em escala.",
        "official_url": "https://aiforgood.itu.int/innovation-factory/",
        "scope": "internacional",
        "country_region": "Suíça (ONU)",
        "country": "Suíça",
        "city": "Genebra",
        "latitude": 46.2280,
        "longitude": 6.1350,
        "ai_requirement": "com_ia",
        "stage_eligibility": "ambos",
        "deadline": "Fluxo contínuo — sessões ao longo do ano",
        "annual_deadline": None,
        "award_status": "aberto",
        "prize_benefits": "Pitch na cúpula global AI for Good, mentoria internacional da ONU, networking com investidores e prêmios parceiros.",
        "categories": ["Inteligência Artificial", "Saúde", "Educação", "Acessibilidade", "Meio Ambiente", "Serviços Públicos Digitais"],
    },
    {
        "title": "World Smart City Awards (Smart City Expo World Congress)",
        "organizer": "Fira de Barcelona",
        "description": "Premiação internacional referência em cidades inteligentes, governança digital, mobilidade, segurança, sustentabilidade e plataformas digitais voltadas ao cidadão (com categorias para projetos em execução e ideias inovadoras).",
        "official_url": "https://www.smartcityexpo.com/world-smart-city-awards/",
        "scope": "internacional",
        "country_region": "Espanha",
        "country": "Espanha",
        "city": "Barcelona",
        "latitude": 41.3851,
        "longitude": 2.1734,
        "ai_requirement": "ambos",
        "stage_eligibility": "ambos",
        "deadline": "Chamada anual até Setembro",
        "annual_deadline": (9, 15),
        "award_status": "aberto",
        "prize_benefits": "Troféu internacional em Barcelona, exposição global no Smart City Expo e networking com governos do mundo todo.",
        "categories": ["Mobilidade", "Governo Digital", "Meio Ambiente", "Segurança", "Serviços Públicos Digitais", "Inclusão"],
    },
    {
        "title": "Bloomberg Philanthropies Mayors Challenge",
        "organizer": "Bloomberg Philanthropies",
        "description": "Competição global para prefeituras e governos locais apresentarem iniciativas inovadoras (ideias/protótipos em desenvolvimento) que resolvam desafios urbanos críticos e melhorem serviços ao cidadão.",
        "official_url": "https://mayorschallenge.bloomberg.org/",
        "scope": "internacional",
        "country_region": "Estados Unidos",
        "country": "Estados Unidos",
        "city": "Nova York",
        "latitude": 40.7614,
        "longitude": -73.9776,
        "ai_requirement": "ambos",
        "stage_eligibility": "iniciativa",
        "deadline": "Rodada bienal (próxima janela prevista Junho)",
        "annual_deadline": (6, 30),
        "award_status": "previsto",
        "prize_benefits": "Financiamento de até US$ 1 milhão para cidades vencedoras + assistência técnica internacional para prototipagem e escala.",
        "categories": ["Serviços Públicos Digitais", "Mobilidade", "Assistência Social", "Saúde", "Meio Ambiente", "Governo Digital"],
    },
    {
        "title": "Open Government Partnership (OGP) Awards",
        "organizer": "Open Government Partnership",
        "description": "Reconhece iniciativas governamentais e cívicas ao redor do mundo que ampliam transparência, participação cidadã, dados abertos e prestação de contas — independente do uso de IA.",
        "official_url": "https://www.opengovpartnership.org/ogp-awards/",
        "scope": "internacional",
        "country_region": "Estados Unidos (Global)",
        "country": "Estados Unidos",
        "city": "Washington, D.C.",
        "latitude": 38.9072,
        "longitude": -77.0369,
        "ai_requirement": "sem_ia",
        "stage_eligibility": "producao",
        "deadline": "Ciclo OGP Global Summit (até Julho)",
        "annual_deadline": (7, 20),
        "award_status": "recorrente",
        "prize_benefits": "Reconhecimento internacional na Cúpula Global da OGP e destaque nos relatórios globais de governo aberto.",
        "categories": ["Transparência", "Participação Cidadã", "Governo Digital", "Serviços Públicos Digitais"],
    },
    {
        "title": "Prêmio Excelência em Competitividade — Boas Práticas (CLP)",
        "organizer": "Centro de Liderança Pública (CLP)",
        "description": "Premia iniciativas e sistemas públicos brasileiros (estados e municípios) com impacto comprovado na eficiência da máquina pública e qualidade dos serviços entregues ao cidadão.",
        "official_url": "https://rankingdecompetitividade.org.br/",
        "scope": "nacional",
        "country_region": "Brasil",
        "country": "Brasil",
        "city": "São Paulo",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "ai_requirement": "ambos",
        "stage_eligibility": "producao",
        "deadline": "Chamada anual até Junho",
        "annual_deadline": (6, 15),
        "award_status": "aberto",
        "prize_benefits": "Selo de Excelência CLP, divulgação nacional para gestores públicos e apresentação no evento oficial.",
        "categories": ["Serviços Públicos Digitais", "Educação", "Saúde", "Segurança", "Governo Digital", "Transparência"],
    },
    {
        "title": "Prêmio ABEP-TIC de Excelência em Governo Digital (SECOP)",
        "organizer": "ABEP-TIC (Associação Brasileira de Entidades Estaduais e Públicas de TIC)",
        "description": "Principal premiação brasileira voltada especificamente para softwares, portais e soluções de tecnologia da informação pública desenvolvidas para atender o cidadão.",
        "official_url": "https://www.abep-tic.org.br/",
        "scope": "nacional",
        "country_region": "Brasil",
        "country": "Brasil",
        "city": "Brasília",
        "latitude": -15.8267,
        "longitude": -47.9218,
        "ai_requirement": "ambos",
        "stage_eligibility": "producao",
        "deadline": "Edital anual SECOP (até Julho)",
        "annual_deadline": (7, 15),
        "award_status": "aberto",
        "prize_benefits": "Prêmio nacional de referência em TIC pública (categorias Melhor Solução de Governo Digital e Inclusão Digital).",
        "categories": ["Governo Digital", "Serviços Públicos Digitais", "Inteligência Artificial", "Transparência", "Saúde", "Educação"],
    },
    {
        "title": "OECD OPSI — Observatory of Public Sector Innovation Call",
        "organizer": "OCDE (OECD OPSI)",
        "description": "Chamada mundial da OCDE para catalogar e destacar inovações do setor público (iniciativas emergentes e soluções consolidadas, com ou sem IA) no relatório Global Trends in Government Innovation.",
        "official_url": "https://oecd-opsi.org/",
        "scope": "internacional",
        "country_region": "França (OCDE)",
        "country": "França",
        "city": "Paris",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "ai_requirement": "ambos",
        "stage_eligibility": "ambos",
        "deadline": "Fluxo contínuo — submissões abertas o ano todo",
        "annual_deadline": None,
        "award_status": "aberto",
        "prize_benefits": "Publicação internacional no relatório da OCDE, vitrine global de inovação pública e convite para fóruns internacionais.",
        "categories": ["Governo Digital", "Serviços Públicos Digitais", "Inteligência Artificial", "Transparência", "Assistência Social", "Educação"],
    },
    {
        "title": "MIT Solve — Global Challenges (Civic & Digital Inclusion)",
        "organizer": "Massachusetts Institute of Technology (MIT)",
        "description": "Desafio global do MIT para iniciativas tecnológicas em desenvolvimento ou estágio inicial que resolvem problemas públicos e sociais críticos com foco no cidadão (saúde, aprendizagem, inclusão econômica e clima).",
        "official_url": "https://solve.mit.edu/challenges",
        "scope": "internacional",
        "country_region": "Estados Unidos (MIT)",
        "country": "Estados Unidos",
        "city": "Cambridge (Boston)",
        "latitude": 42.3601,
        "longitude": -71.0942,
        "ai_requirement": "ambos",
        "stage_eligibility": "iniciativa",
        "deadline": "Ciclo anual (até Abril)",
        "annual_deadline": (4, 18),
        "award_status": "aberto",
        "prize_benefits": "Fundo inicial a partir de US$ 10.000 + acesso a mais de US$ 1M em prêmios parceiros e programa de apoio do MIT.",
        "categories": ["Saúde", "Educação", "Assistência Social", "Meio Ambiente", "Inclusão", "Serviços Públicos Digitais"],
    },
    {
        "title": "Digital Public Goods Alliance (DPGA) Registry",
        "organizer": "Digital Public Goods Alliance (UNICEF / ONU parceiros)",
        "description": "Certificação e reconhecimento internacional para softwares de código aberto e dados abertos que atuam como Bens Públicos Digitais para atender cidadãos em escala global.",
        "official_url": "https://digitalpublicgoods.net/registry/",
        "scope": "internacional",
        "country_region": "Noruega (Global)",
        "country": "Noruega",
        "city": "Oslo",
        "latitude": 59.9139,
        "longitude": 10.7522,
        "ai_requirement": "ambos",
        "stage_eligibility": "ambos",
        "deadline": "Fluxo contínuo durante todo o ano",
        "annual_deadline": None,
        "award_status": "aberto",
        "prize_benefits": "Selo oficial de Digital Public Good (ONU), visibilidade para financiamento internacional e adoção por governos.",
        "categories": ["Governo Digital", "Serviços Públicos Digitais", "Saúde", "Educação", "Transparência"],
    },
    {
        "title": "Premios Latinoamérica Verde / Premios Verdes & Impacto Cívico",
        "organizer": "Fundación Premios Verdes",
        "description": "Maior premiação da América Latina para iniciativas e tecnologias (em desenvolvimento ou operação) com impacto social, urbano, ambiental e de atendimento ao cidadão.",
        "official_url": "https://premiosverdes.org/",
        "scope": "regional",
        "country_region": "Equador (América Latina)",
        "country": "Equador",
        "city": "Guayaquil",
        "latitude": -2.1894,
        "longitude": -79.8891,
        "ai_requirement": "ambos",
        "stage_eligibility": "ambos",
        "deadline": "Inscrições anuais até Janeiro",
        "annual_deadline": (1, 31),
        "award_status": "aberto",
        "prize_benefits": "Certificação Top 500 LATAM, aceleração, mídia regional e premiação internacional.",
        "categories": ["Meio Ambiente", "Mobilidade", "Assistência Social", "Serviços Públicos Digitais", "Educação"],
    },
    {
        "title": "IDC Smart Cities & Digital Government Awards",
        "organizer": "IDC (International Data Corporation)",
        "description": "Premiação internacional por regiões (incluindo América Latina e Global) para projetos de software governamental, atendimento digital ao cidadão, dados e IA no setor público.",
        "official_url": "https://www.idc.com/",
        "scope": "internacional",
        "country_region": "Reino Unido / Global",
        "country": "Reino Unido",
        "city": "Londres",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "ai_requirement": "ambos",
        "stage_eligibility": "producao",
        "deadline": "Chamada anual por região (até Agosto)",
        "annual_deadline": (8, 30),
        "award_status": "aberto",
        "prize_benefits": "Reconhecimento IDC de excelência tecnológica governamental e divulgação em relatórios executivos internacionais.",
        "categories": ["Governo Digital", "Serviços Públicos Digitais", "Inteligência Artificial", "Mobilidade", "Segurança", "Educação"],
    },
]


def _award_fingerprint(title: str, organizer: str) -> str:
    norm = f"{title.strip().lower()}|{organizer.strip().lower()}"
    return hashlib.sha256(norm.encode("utf-8", errors="ignore")).hexdigest()


def _score_curated_award(system: MonitoredSystem, award: dict[str, Any]) -> tuple[int, str, str]:
    score = 52
    reasons: list[str] = []

    sys_ai = system.uses_ai
    req_ai = award["ai_requirement"]
    if req_ai == "ambos":
        score += 14
        reasons.append("Aceita soluções com ou sem IA, compatível com o perfil técnico do sistema.")
    elif req_ai == "com_ia":
        if sys_ai in {"com_ia", "hibrido"}:
            score += 22
            reasons.append("Foco em IA alinha-se diretamente ao uso de Inteligência Artificial no sistema.")
        else:
            score -= 26
            reasons.append("Exige componente de IA (o sistema atual está marcado como sem IA).")
    elif req_ai == "sem_ia":
        score += 14
        reasons.append("Não exige IA — avalia impacto cidadão e transparência independente da tecnologia.")

    sys_stage = system.stage
    elig_stage = award["stage_eligibility"]
    if elig_stage == "ambos":
        score += 14
        reasons.append("Elegível tanto para iniciativas em desenvolvimento quanto para sistemas já em operação.")
    elif elig_stage == sys_stage:
        score += 18
        label = "iniciativas/protótipos" if sys_stage == "iniciativa" else "sistemas já em produção"
        reasons.append(f"Estágio ideal: o edital busca exatamente {label}.")
    else:
        score -= 14
        needed = "sistema já em operação" if elig_stage == "producao" else "iniciativa em fase inicial"
        reasons.append(f"Atenção ao estágio: o prêmio prioriza {needed}.")

    area = (system.citizen_area or "").lower()
    desc_blob = f"{system.name} {system.description} {system.impact_summary} {system.target_audience}".lower()
    cat_matches = [c for c in award.get("categories", []) if c.lower() in area or area in c.lower() or c.lower() in desc_blob]
    if cat_matches:
        score += min(16, 8 + 4 * len(cat_matches))
        reasons.append(f"Alta afinidade temática em: {', '.join(cat_matches[:3])}.")

    sys_country = (system.country or "Brasil").lower()
    if award["scope"] == "nacional" and "brasil" in sys_country:
        score += 8
        reasons.append("Prêmio nacional brasileiro com forte aderência institucional.")
    elif award["scope"] == "internacional":
        score += 6
        reasons.append("Visibilidade internacional para projetos de atendimento ao cidadão.")

    final_score = max(15, min(98, score))
    reasoning = " ".join(reasons)
    next_steps = (
        f"1) Acessar o edital oficial ({award['organizer']}); "
        f"2) Preparar resumo de impacto para {system.target_audience or 'os cidadãos'}; "
        f"3) Documentar evidências de resultados e arquitetura ({'destacando o uso de IA' if sys_ai != 'sem_ia' else 'destacando simplicidade, acessibilidade e alcance'})."
    )
    return final_score, reasoning, next_steps


async def discover_awards_with_gemini(
    system: MonitoredSystem,
    runtime_config: dict[str, Any],
    focus_scope: str = "todos",
    include_ai_filter: str = "auto",
) -> list[dict[str, Any]]:
    """Search globally for open awards (>= 15 days ahead) using Gemini + Grounding or DDGS Free Tier synthesis."""
    api_key = runtime_config.get("gemini_api_key", "")
    if not api_key:
        return []

    model = runtime_config.get("gemini_model", "gemini-4-hydrogen")
    today_iso = date.today().isoformat()
    stage_text = (
        "Iniciativa / protótipo / em desenvolvimento"
        if system.stage == "iniciativa"
        else "Sistema já desenvolvido e em produção atendendo o cidadão"
    )
    ai_text = {
        "com_ia": f"Sim, usa IA ({system.ai_details or 'Inteligência Artificial integrada'})",
        "hibrido": f"Híbrido — módulos com e sem IA ({system.ai_details or 'recursos assistivos de IA'})",
        "sem_ia": "Não utiliza IA (software tradicional voltado ao cidadão)",
    }.get(system.uses_ai, system.uses_ai)

    scope_instruction = {
        "nacional": f"Foque prioritariamente em premiações e concursos nacionais de {system.country}.",
        "internacional": "Foque prioritariamente em premiações e concursos internacionais em todo o mundo (ONU, Europa, EUA, LATAM, Ásia, Global).",
        "todos": f"Pesquise em TODO O MUNDO — combinando premiações internacionais globais e premiações nacionais de {system.country}.",
    }.get(focus_scope, "Pesquise em todo o mundo.")

    ai_filter_instruction = {
        "com_ia": "Priorize premiações voltadas a soluções com IA para atendimento ao cidadão.",
        "sem_ia": "Priorize premiações que NÃO exigem IA (abertas a software cívico/público tradicional).",
        "ambos": "Inclua premiações tanto específicas de IA quanto abertas a sistemas sem IA.",
        "auto": "Ajuste os prêmios encontrados ao perfil de IA do sistema descrito abaixo (incluindo editais abertos a soluções com ou sem IA).",
    }.get(include_ai_filter, "")

    location_parts = [p for p in [getattr(system, "municipality", ""), getattr(system, "state_uf", ""), system.country] if p]
    location_label = " / ".join(location_parts) or system.country

    prompt = f"""Você é um pesquisador internacional especialista em premiações, concursos, desafios GovTech, CivicTech e inovação em software para atendimento ao cidadão.
DATA DE HOJE: {today_iso}.

PERFIL DO SISTEMA CADASTRADO:
- Nome: {system.name}
- O que o sistema faz: {system.description}
- Estágio atual: {stage_text}
- Uso de IA: {ai_text}
- Área de atendimento ao cidadão: {system.citizen_area}
- Público-alvo cidadão: {system.target_audience}
- Tipo de organização: {system.organization_type}
- Localização (Município / Estado / País): {location_label}
- Impacto esperado/comprovado: {system.impact_summary or "Melhoria direta do atendimento e qualidade de vida do cidadão"}

ESCOPO DA PESQUISA:
{scope_instruction}
{ai_filter_instruction}

REGRAS OBRIGATÓRIAS:
1. Retorne APENAS premiações e concursos que AINDA DÃO PARA SE INSCREVER (prazo futuro com pelo menos 15 dias a partir de {today_iso}, ou fluxo contínuo aberto). NUNCA inclua editais já encerrados.
2. Informe o PAÍS, a CIDADE sede/inscrição e coordenadas (latitude/longitude) de cada premiação para plotagem no mapa mundial.
3. Nunca invente concursos ou URLs falsas. Informe sempre o link oficial real.
4. Retorne EXCLUSIVAMENTE um JSON válido no formato:
{{
  "awards": [
    {{
      "title": "Nome oficial do prêmio ou concurso",
      "organizer": "Instituição organizadora",
      "description": "Resumo claro em português do objetivo da premiação",
      "official_url": "https://link-oficial-real",
      "scope": "nacional" | "regional" | "internacional",
      "country_region": "País ou Região",
      "country": "Nome do País (ex: Brasil, Suíça, Espanha, Estados Unidos)",
      "city": "Nome da Cidade (ex: Brasília, Genebra, Barcelona, Nova York)",
      "latitude": número float opcional,
      "longitude": número float opcional,
      "ai_requirement": "com_ia" | "sem_ia" | "ambos",
      "stage_eligibility": "iniciativa" | "producao" | "ambos",
      "deadline": "Descrição legível do prazo",
      "deadline_date": "YYYY-MM-DD ou vazio se fluxo contínuo",
      "award_status": "aberto" | "previsto" | "recorrente",
      "prize_benefits": "Prêmio em dinheiro, troféu, mentoria, visibilidade, etc.",
      "categories": ["categoria 1", "categoria 2"],
      "match_score": 0 a 100,
      "match_reasoning": "Explicação objetiva em português de por que este prêmio combina com o sistema cadastrado",
      "next_steps": "Passos práticos recomendados para submissão"
    }}
  ]
}}
Retorne entre 6 e 10 oportunidades reais abertas ou futuras.
"""

    output_text, grounding_urls, error = await asyncio.to_thread(
        call_gemini_interaction,
        api_key,
        prompt,
        model,
        True,
        "Responda exclusivamente em JSON válido em português do Brasil com premiações reais encontradas via Google Search.",
    )

    if error or not output_text:
        logger.warning("Gemini grounded awards search unavailable (%s); trying DDGS + Gemini Free Tier synthesis.", error)
        try:
            from ddgs import DDGS

            def _ddgs_awards() -> list[dict[str, str]]:
                queries = [
                    f"prêmio inovação setor público {system.citizen_area} {system.country} inscrições",
                    f"global govtech civic tech award {system.citizen_area} digital citizen open call",
                ]
                found: list[dict[str, str]] = []
                with DDGS() as ddgs:
                    for q in queries:
                        for r in (ddgs.text(q, region="br-pt", max_results=6) or []):
                            found.append({
                                "title": str(r.get("title") or ""),
                                "url": str(r.get("href") or ""),
                                "snippet": str(r.get("body") or ""),
                            })
                return found

            web_hits = await asyncio.to_thread(_ddgs_awards)
            if not web_hits:
                return []

            synthesis_prompt = (
                prompt
                + "\n\nRESULTADOS REAIS COLETADOS NA WEB AGORA (baseie-se EXCLUSIVAMENTE nestas URLs e dados reais):\n"
                + json.dumps(web_hits[:12], ensure_ascii=False)
            )
            output_text, grounding_urls, error = await asyncio.to_thread(
                call_gemini_interaction,
                api_key,
                synthesis_prompt,
                model,
                False,
                "Extraia e estruture apenas premiações/concursos REAIS presentes nos resultados fornecidos, respondendo exclusivamente em JSON válido.",
            )
        except Exception as exc:
            logger.warning("DDGS awards fallback failed: %s", exc)
            return []

    if error or not output_text:
        logger.warning("Gemini awards search failed: %s", error)
        return []

    payload = extract_json_payload(output_text)
    raw_awards = payload.get("awards", []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_awards):
        if not isinstance(item, dict) or not item.get("title"):
            continue
        url = str(item.get("official_url", "")).strip()
        if not url and idx < len(grounding_urls):
            url = grounding_urls[idx].get("url", "")

        status = str(item.get("award_status", "aberto")).lower()
        if status not in {"aberto", "previsto", "recorrente", "encerrado"}:
            status = "recorrente"

        raw_deadline_date = str(item.get("deadline_date", "") or "").strip()
        parsed_d = parse_deadline_date(raw_deadline_date)
        iso_deadline = parsed_d.isoformat() if parsed_d else ""

        # Skip awards whose deadline already passed or is < 15 days away!
        is_open, _ = is_award_open_with_buffer(status, iso_deadline, min_days_ahead=15)
        if not is_open:
            continue

        ai_req = str(item.get("ai_requirement", "ambos")).lower()
        if ai_req not in {"com_ia", "sem_ia", "ambos"}:
            ai_req = "ambos"
        stage_elig = str(item.get("stage_eligibility", "ambos")).lower()
        if stage_elig not in {"iniciativa", "producao", "ambos"}:
            stage_elig = "ambos"
        scope = str(item.get("scope", "internacional")).lower()
        if scope not in {"nacional", "regional", "internacional"}:
            scope = "internacional"

        try:
            score = max(10, min(100, int(item.get("match_score", 75))))
        except (TypeError, ValueError):
            score = 75

        raw_lat = item.get("latitude")
        raw_lng = item.get("longitude")
        try:
            lat = float(raw_lat) if raw_lat is not None else None
            lng = float(raw_lng) if raw_lng is not None else None
        except (TypeError, ValueError):
            lat, lng = None, None

        country, city, lat, lng = resolve_award_geolocation(
            country=str(item.get("country", "")),
            city=str(item.get("city", "")),
            country_region=str(item.get("country_region", "Global")),
            latitude=lat,
            longitude=lng,
        )

        normalized.append(
            {
                "title": str(item.get("title", ""))[:290],
                "organizer": str(item.get("organizer", ""))[:240],
                "description": str(item.get("description", ""))[:2000],
                "official_url": url[:990],
                "scope": scope,
                "country_region": str(item.get("country_region", country))[:110],
                "country": country[:95],
                "city": city[:115],
                "latitude": lat,
                "longitude": lng,
                "ai_requirement": ai_req,
                "stage_eligibility": stage_elig,
                "deadline": str(item.get("deadline", "Verificar edital"))[:115],
                "deadline_date": iso_deadline,
                "award_status": status,
                "prize_benefits": str(item.get("prize_benefits", ""))[:1000],
                "categories": item.get("categories") if isinstance(item.get("categories"), list) else [],
                "match_score": score,
                "match_reasoning": str(item.get("match_reasoning", ""))[:1000],
                "next_steps": str(item.get("next_steps", ""))[:1000],
                "discovery_source": "gemini_global_search",
            }
        )

    return normalized


CLOSED_PHRASES = [
    "inscrições encerradas",
    "inscricoes encerradas",
    "prazo encerrado",
    "período de inscrições encerrado",
    "submissões encerradas",
    "applications closed",
    "submissions closed",
    "nominations closed",
    "registration closed",
    "call is now closed",
    "has closed",
    "encerradas as inscrições",
]

OPEN_PHRASES = [
    "inscrições abertas",
    "inscricoes abertas",
    "inscreva-se",
    "faça sua inscrição",
    "applications open",
    "submissions open",
    "nominations open",
    "submit your project",
    "apply now",
    "fluxo contínuo",
    "rolling basis",
]


SUBLINK_PRIORITY_TERMS = (
    "inscri", "edital", "regulamento", "cronograma", "premio", "prêmio",
    "apply", "submit", "submission", "nominat", "deadline", "call", "challenge", "awards",
)


def _extract_relevant_sublinks(base_url: str, html_text: str, limit: int = 2) -> list[str]:
    """Find internal links on the official site that lead to registration / edital / deadline pages."""
    try:
        base_host = urlparse(base_url).netloc.replace("www.", "").lower()
    except Exception:
        return []
    if not base_host:
        return []

    scored: list[tuple[int, str]] = []
    seen: set[str] = {base_url.rstrip("/")}

    for href, anchor_text in re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>([\s\S]*?)</a>', html_text, flags=re.I):
        full_url = urljoin(base_url, href.strip())
        parsed = urlparse(full_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.replace("www.", "").lower() != base_host:
            continue
        norm_url = full_url.rstrip("/")
        if norm_url in seen or norm_url.lower().endswith((".pdf", ".jpg", ".png", ".zip", ".mp4")):
            continue
        seen.add(norm_url)

        combined = f"{parsed.path} {strip_html(anchor_text)}".lower()
        score = sum(2 if term in parsed.path.lower() else 1 for term in SUBLINK_PRIORITY_TERMS if term in combined)
        if score > 0:
            scored.append((score, full_url))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in scored[:limit]]


async def _fetch_official_page_and_sublinks(official_url: str) -> tuple[str, list[str], str]:
    """
    Enter the award's official page AND follow up to 2 relevant internal subpages
    (e.g. /edital, /inscricoes, /premio-conexao-inova) to inspect actual open/closed dates.
    Returns (combined_clean_text, visited_urls, status_note).
    """
    if not official_url:
        return "", [], "Sem URL oficial"

    visited: list[str] = []
    chunks: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; CidadaoPulse/1.0)"}
            resp = await client.get(official_url, headers=headers)
            if resp.status_code != 200 or not resp.text:
                return "", [], f"Site oficial retornou HTTP {resp.status_code}"

            visited.append(str(resp.url))
            cleaned_home = re.sub(r"<(script|style|noscript)[^>]*>[\s\S]*?</\1>", " ", resp.text, flags=re.I)
            chunks.append(f"[PÁGINA PRINCIPAL {resp.url}]\n{strip_html(cleaned_home)[:2400]}")

            sublinks = _extract_relevant_sublinks(str(resp.url), resp.text, limit=2)
            for sub_url in sublinks:
                try:
                    s_resp = await client.get(sub_url, headers=headers)
                    if s_resp.status_code == 200 and s_resp.text:
                        visited.append(str(s_resp.url))
                        s_clean = re.sub(r"<(script|style|noscript)[^>]*>[\s\S]*?</\1>", " ", s_resp.text, flags=re.I)
                        chunks.append(f"[SUBPÁGINA {s_resp.url}]\n{strip_html(s_clean)[:1800]}")
                except Exception:
                    continue

            return "\n\n".join(chunks), visited, f"Varredura em {len(visited)} página(s) oficial(is)"
    except Exception as exc:
        return "", visited, f"Site oficial indisponível ({str(exc)[:60]})"


async def verify_single_award_deadline_live(
    award: AwardOpportunity,
    runtime_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Enter the award's official webpage + internal edital/inscrições subpages + web search snippets
    to verify whether registrations are ACTUALLY OPEN today, CLOSED, or UPCOMING.
    """
    today_iso = date.today().isoformat()
    page_text, visited_urls, fetch_note = await _fetch_official_page_and_sublinks(award.official_url)

    # 2. Complement with live DDGS web search for current registration dates
    search_snippets = ""
    try:
        from ddgs import DDGS

        def _search_deadline():
            q = f'"{award.title}" inscrições OR prazo OR deadline OR submissions'
            with DDGS() as ddgs:
                rows = ddgs.text(q, region="br-pt", max_results=4) or []
                return " | ".join(
                    f"{strip_html(str(r.get('title') or ''))}: {strip_html(str(r.get('body') or ''))}"
                    for r in rows
                )

        search_snippets = await asyncio.to_thread(_search_deadline)
    except Exception:
        pass

    combined_text = f"{page_text}\n\nBUSCA WEB:\n{search_snippets}".strip()
    if not combined_text:
        return {
            "award_status": "previsto" if award.award_status == "aberto" else award.award_status,
            "deadline": award.deadline,
            "deadline_date": award.deadline_date,
            "source_note": fetch_note or "Não foi possível consultar a página oficial agora.",
        }

    # 3. Prefer Gemini Free Tier (gemini-3.5-flash-lite) for accurate date/status extraction
    api_key = runtime_config.get("gemini_api_key", "")
    model = runtime_config.get("gemini_model", "gemini-3.5-flash-lite")
    if api_key:
        prompt = f"""Você é um auditor rigoroso de editais e premiações.
DATA DE HOJE: {today_iso}.
PRÊMIO: {award.title} ({award.organizer})
PÁGINAS OFICIAIS VARRIDAS: {", ".join(visited_urls) if visited_urls else award.official_url}

TEXTO EXTRAÍDO DO SITE OFICIAL (PÁGINA + SUBPÁGINAS DE EDITAL/INSCRIÇÕES) E BUSCA WEB:
{combined_text[:4500]}

Analise com RIGOR ABSOLUTO se as inscrições estão REALMENTE ABERTAS HOJE ({today_iso}) ou se o prazo JÁ PASSOU / ESTÁ ENCERRADO / AGUARDANDO PRÓXIMO EDITAL.
REGRAS:
- NUNCA responda "aberto" se o texto indicar que a última edição já encerrou, se a cerimônia já aconteceu ou se a data limite encontrada for anterior a {today_iso}.
- Só responda "aberto" se houver evidência clara de inscrições/submissões vigentes hoje (data futura ≥ {today_iso} ou fluxo contínuo aberto).

Retorne EXCLUSIVAMENTE um JSON válido:
{{
  "award_status": "aberto" | "previsto" | "encerrado",
  "deadline_date": "YYYY-MM-DD se houver data limite futura real confirmada, senão string vazia ''",
  "deadline_label": "Resumo curto do prazo real (ex: 'Inscrições encerradas', 'Fluxo contínuo aberto', 'Aberto até 15/02/2027', 'Aguardando próximo edital')",
  "evidence": "Evidência curta em português (1 frase) explicando o status encontrado na página oficial"
}}
"""
        out_text, _, err = await asyncio.to_thread(
            call_gemini_interaction,
            api_key,
            prompt,
            model,
            False,
            "Seja rigoroso e conservador: responda apenas em JSON válido em português.",
            20.0,
        )
        parsed = extract_json_payload(out_text) if out_text and not err else None
        if isinstance(parsed, dict) and parsed.get("award_status") in {"aberto", "previsto", "encerrado"}:
            st = parsed["award_status"]
            d_raw = str(parsed.get("deadline_date") or "").strip()
            d_parsed = parse_deadline_date(d_raw)
            iso_d = d_parsed.isoformat() if d_parsed else ""
            if d_parsed and (d_parsed - date.today()).days < 0:
                st = "encerrado"
            return {
                "award_status": st,
                "deadline": str(parsed.get("deadline_label") or award.deadline)[:115],
                "deadline_date": iso_d,
                "source_note": f"{fetch_note} em {date.today().strftime('%d/%m/%Y')}: {str(parsed.get('evidence') or '')}"[:400],
            }

    # 4. Local deterministic fallback if Gemini unavailable
    low = combined_text.lower()
    if any(p in low for p in CLOSED_PHRASES):
        return {
            "award_status": "encerrado",
            "deadline": "Inscrições encerradas (verificado na página)",
            "deadline_date": "",
            "source_note": f"{fetch_note} em {date.today().strftime('%d/%m/%Y')}: página indica inscrições encerradas.",
        }
    if any(p in low for p in OPEN_PHRASES):
        return {
            "award_status": "aberto",
            "deadline": award.deadline,
            "deadline_date": award.deadline_date,
            "source_note": f"{fetch_note} em {date.today().strftime('%d/%m/%Y')}: página indica inscrições/submissões abertas.",
        }
    return {
        "award_status": "previsto",
        "deadline": award.deadline,
        "deadline_date": award.deadline_date,
        "source_note": f"{fetch_note} em {date.today().strftime('%d/%m/%Y')}: sem confirmação explícita de edital aberto hoje.",
    }


async def verify_awards_deadlines_live(
    db: Session,
    runtime_config: dict[str, Any],
    system_id: int | None = None,
    only_stale_hours: int | None = None,
) -> dict[str, Any]:
    """Verify deadlines live by entering each award's official page & subpages."""
    q = db.query(AwardOpportunity)
    if system_id is not None:
        q = q.filter(AwardOpportunity.system_id == system_id)
    rows = q.all()

    now = datetime.now(timezone.utc)
    to_check: list[AwardOpportunity] = []
    for r in rows:
        # Respect manual user override ("Marcado como encerrado pelo usuário")
        if "marcado como encerrado pelo usuário" in (r.deadline_source_note or "").lower():
            continue
        if only_stale_hours is not None and r.deadline_verified_at is not None:
            ver_dt = r.deadline_verified_at
            if ver_dt.tzinfo is None:
                ver_dt = ver_dt.replace(tzinfo=timezone.utc)
            if (now - ver_dt) < timedelta(hours=only_stale_hours):
                continue
        to_check.append(r)

    sem = asyncio.Semaphore(4)

    async def _check(row: AwardOpportunity):
        async with sem:
            res = await verify_single_award_deadline_live(row, runtime_config)
            return row, res

    results = await asyncio.gather(*[_check(r) for r in to_check], return_exceptions=True)

    counts = {"checked": 0, "aberto": 0, "previsto": 0, "encerrado": 0}
    for item in results:
        if isinstance(item, Exception):
            continue
        row, res = item
        row.award_status = res["award_status"]
        row.deadline = res["deadline"]
        row.deadline_date = res["deadline_date"]
        row.deadline_verified_at = now
        row.deadline_source_note = res["source_note"]
        counts["checked"] += 1
        if res["award_status"] in counts:
            counts[res["award_status"]] += 1

    db.commit()
    return counts


def enrich_existing_awards_metadata(db: Session) -> int:
    """Backfill country, city, lat/lng and next upcoming deadline_date for existing DB awards."""
    by_fp = {_award_fingerprint(a["title"], a["organizer"]): a for a in CURATED_GLOBAL_AWARDS}
    updated = 0
    for row in db.query(AwardOpportunity).all():
        curated = by_fp.get(row.fingerprint)
        changed = False
        if curated:
            if not row.country or not row.city or row.latitude is None or row.longitude is None:
                row.country = curated["country"]
                row.city = curated["city"]
                row.latitude = curated["latitude"]
                row.longitude = curated["longitude"]
                changed = True
            if not row.deadline_date and curated.get("annual_deadline") and row.deadline_verified_at is None:
                mo, dy = curated["annual_deadline"]
                row.deadline_date = next_annual_date(mo, dy, min_days_ahead=15)
                row.deadline = curated["deadline"]
                if row.award_status != "encerrado":
                    row.award_status = "previsto"
                changed = True
        else:
            if not row.country or not row.city or row.latitude is None or row.longitude is None:
                c, ci, lat, lng = resolve_award_geolocation(
                    country=row.country, city=row.city, country_region=row.country_region,
                    latitude=row.latitude, longitude=row.longitude,
                )
                row.country, row.city, row.latitude, row.longitude = c, ci, lat, lng
                changed = True
        if changed:
            updated += 1
    if updated:
        db.commit()
    return updated


async def run_awards_radar_for_system(
    db: Session,
    system: MonitoredSystem,
    runtime_config: dict[str, Any],
    focus_scope: str = "todos",
    include_ai_filter: str = "auto",
) -> tuple[int, int, list[AwardOpportunity]]:
    """
    Execute global awards search for a single system.
    Only keeps awards with >= 15 days left to apply (or rolling/continuous).
    """
    candidates: list[dict[str, Any]] = []

    live_awards = await discover_awards_with_gemini(
        system, runtime_config, focus_scope=focus_scope, include_ai_filter=include_ai_filter
    )
    candidates.extend(live_awards)

    for curated in CURATED_GLOBAL_AWARDS:
        if focus_scope != "todos" and curated["scope"] != focus_scope:
            if not (focus_scope == "internacional" and curated["scope"] == "regional"):
                continue
        if include_ai_filter == "com_ia" and curated["ai_requirement"] == "sem_ia":
            continue
        if include_ai_filter == "sem_ia" and curated["ai_requirement"] == "com_ia":
            continue

        score, reasoning, next_steps = _score_curated_award(system, curated)
        if include_ai_filter == "auto" and score < 40:
            continue

        annual = curated.get("annual_deadline")
        iso_deadline = next_annual_date(annual[0], annual[1], min_days_ahead=15) if annual else ""

        candidates.append(
            {
                **curated,
                "deadline_date": iso_deadline,
                "match_score": score,
                "match_reasoning": reasoning,
                "next_steps": next_steps,
                "discovery_source": "curated_catalog",
            }
        )

    new_count = 0
    new_records: list[AwardOpportunity] = []
    seen_fps: set[str] = set()

    for cand in candidates:
        fp = _award_fingerprint(cand["title"], cand.get("organizer", ""))
        if fp in seen_fps:
            continue
        seen_fps.add(fp)

        existing = (
            db.query(AwardOpportunity)
            .filter(AwardOpportunity.system_id == system.id, AwardOpportunity.fingerprint == fp)
            .first()
        )
        if existing:
            # Update match & geolocation, but NEVER overwrite a live-verified or manually-closed award_status with static catalog data!
            existing.match_score = cand["match_score"]
            existing.match_reasoning = cand["match_reasoning"]
            existing.country = cand.get("country", existing.country)
            existing.city = cand.get("city", existing.city)
            existing.latitude = cand.get("latitude", existing.latitude)
            existing.longitude = cand.get("longitude", existing.longitude)
            if cand.get("official_url"):
                existing.official_url = cand["official_url"]

            is_manually_closed = "marcado como encerrado pelo usuário" in (existing.deadline_source_note or "").lower()
            is_already_verified = existing.deadline_verified_at is not None
            if not is_manually_closed and not is_already_verified:
                if cand["discovery_source"] == "gemini_global_search":
                    existing.deadline = cand["deadline"]
                    existing.deadline_date = cand.get("deadline_date", "")
                    existing.award_status = cand["award_status"]
            continue

        # Curated seasonal awards without live confirmation start as 'previsto' until verified on their official page!
        initial_status = cand.get("award_status", "previsto")
        if cand["discovery_source"] == "curated_catalog" and cand.get("annual_deadline") is not None:
            initial_status = "previsto"

        record = AwardOpportunity(
            system_id=system.id,
            fingerprint=fp,
            title=cand["title"],
            organizer=cand.get("organizer", ""),
            description=cand.get("description", ""),
            official_url=cand.get("official_url", ""),
            scope=cand.get("scope", "internacional"),
            country_region=cand.get("country_region", "Global"),
            country=cand.get("country", ""),
            city=cand.get("city", ""),
            latitude=cand.get("latitude"),
            longitude=cand.get("longitude"),
            ai_requirement=cand.get("ai_requirement", "ambos"),
            stage_eligibility=cand.get("stage_eligibility", "ambos"),
            deadline=cand.get("deadline", "Verificar edital"),
            deadline_date=cand.get("deadline_date", ""),
            award_status=initial_status,
            prize_benefits=cand.get("prize_benefits", ""),
            categories_json=json.dumps(cand.get("categories", []), ensure_ascii=False),
            match_score=cand["match_score"],
            match_reasoning=cand["match_reasoning"],
            next_steps=cand["next_steps"],
            discovery_source=cand["discovery_source"],
            pipeline_status="novo",
            user_notes="",
        )
        db.add(record)
        new_records.append(record)
        new_count += 1

    db.commit()
    for rec in new_records:
        db.refresh(rec)

    # Automatically crawl official pages (+ edital/inscrições subpages) for any unverified/stale (>24h) awards
    # whenever Gemini is configured (live mode) so closed calls are NEVER shown as open!
    if runtime_config.get("gemini_api_key"):
        await verify_awards_deadlines_live(
            db, runtime_config, system_id=system.id, only_stale_hours=24
        )
        for rec in new_records:
            db.refresh(rec)

    open_new = [r for r in new_records if r.award_status == "aberto"]
    open_new.sort(key=lambda a: a.match_score, reverse=True)
    return len(seen_fps), new_count, open_new[:5]
