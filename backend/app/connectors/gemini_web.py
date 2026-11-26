from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import (
    BaseConnector,
    CollectedMention,
    extract_search_terms,
    infer_platform_from_url,
)
from app.services.gemini_client import call_gemini_interaction, extract_json_payload

logger = logging.getLogger(__name__)


class GeminiWebSearchConnector(BaseConnector):
    id = "gemini_web"
    name = "Gemini Web & Social Grounding"
    category = "ia_busca_web"
    description = (
        "Usa a Gemini API (gemini-4-hydrogen) com Google Search Grounding para varrer toda a internet: "
        "notícias, portais, Reclame Aqui, lojas de apps, fóruns e menções públicas em redes sociais (X, Instagram, Facebook, LinkedIn, YouTube, TikTok)."
    )
    requires_key = True
    env_var = "GEMINI_API_KEY"
    platforms = ["web", "news", "x", "instagram", "facebook", "linkedin", "youtube", "reclame_aqui", "app_store"]

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 12,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        api_key = runtime_config.get("gemini_api_key", "")
        if not api_key:
            return []

        model = runtime_config.get("gemini_model", "gemini-4-hydrogen")
        terms = extract_search_terms(system)
        try:
            urls = json.loads(system.urls_json or "[]")
        except json.JSONDecodeError:
            urls = []

        window_text = (
            f"últimos {lookback_days} dias"
            if lookback_days <= 30
            else ("últimos 6 meses" if lookback_days <= 185 else "último 1 ano")
        )

        location_parts = [p for p in [getattr(system, "municipality", ""), getattr(system, "state_uf", ""), system.country] if p]
        location_str = " / ".join(location_parts) or system.country

        prompt = f"""Você é um analista de monitoramento digital e reputação de sistemas públicos/cívicos.
Pesquise na internet e em páginas públicas de redes sociais (notícias, portais, Reclame Aqui, Google Play/App Store, YouTube, X/Twitter, Instagram, Facebook, LinkedIn, Reddit e fóruns) por menções reais publicadas nos {window_text} sobre o sistema abaixo.

SISTEMA MONITORADO:
- Nome: {system.name}
- Descrição: {system.description}
- Esfera / Organização: {system.organization_type}
- Localização / Jurisdição: {location_str}
- URLs oficiais: {", ".join(urls) if urls else "Não informadas"}
- Palavras-chave / aliases: {", ".join(terms)}

INSTRUÇÕES IMPORTANTES:
1. Busque menções reais e recentes (elogios, reclamações, notícias, avaliações de usuários, discussões em redes sociais ou fóruns) que sejam ESTRITAMENTE sobre este sistema específico ({system.name} — {system.citizen_area}, {system.organization_type}).
2. DESCARTE completamente resultados sobre outros assuntos que apenas compartilhem uma sigla parecida (ex.: esportes, Fórmula 1, empresas ou órgãos de outros estados/países sem relação com o sistema descrito).
3. NUNCA invente URLs ou menções fictícias. Retorne apenas resultados reais encontrados na busca com links diretos reais.
4. Retorne EXCLUSIVAMENTE um JSON válido com a estrutura:
{{
  "mentions": [
    {{
      "title": "Título curto ou resumo da postagem/matéria",
      "content": "Trecho relevante da opinião, notícia ou avaliação do cidadão",
      "url": "https://url-real-encontrada",
      "platform": "web|news|x|instagram|facebook|linkedin|youtube|reddit|reclame_aqui|app_store|forum",
      "author": "Nome do portal, canal ou autor",
      "matched_keyword": "palavra-chave ou URL correspondente",
      "published_at": "YYYY-MM-DD ou vazio se desconhecida"
    }}
  ]
}}
Retorne até {max_results} menções mais relevantes e diversas.
"""

        output_text, grounding_urls, error = await asyncio.to_thread(
            call_gemini_interaction,
            api_key,
            prompt,
            model,
            True,
            "Responda somente em JSON válido em português do Brasil, baseando-se exclusivamente em resultados reais do Google Search.",
        )

        if error or not output_text:
            logger.warning("GeminiWebSearchConnector error: %s", error)
            return []

        payload = extract_json_payload(output_text)
        raw_items = []
        if isinstance(payload, dict):
            raw_items = payload.get("mentions", [])
        elif isinstance(payload, list):
            raw_items = payload

        mentions: list[CollectedMention] = []
        for idx, item in enumerate(raw_items[:max_results]):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url and idx < len(grounding_urls):
                url = grounding_urls[idx].get("url", "")
            title = str(item.get("title", "")).strip()
            content = str(item.get("content", "")).strip()
            if not title and not content:
                continue

            pub_dt = None
            raw_pub = str(item.get("published_at", "")).strip()
            if raw_pub:
                try:
                    pub_dt = datetime.fromisoformat(raw_pub[:10]).replace(tzinfo=timezone.utc)
                except ValueError:
                    pub_dt = None

            raw_platform = str(item.get("platform", "")).strip().lower()
            platform = raw_platform if raw_platform in {
                "web", "news", "x", "instagram", "facebook", "linkedin",
                "youtube", "tiktok", "reddit", "reclame_aqui", "app_store", "forum"
            } else infer_platform_from_url(url, "web")

            mentions.append(
                CollectedMention(
                    source_connector=self.id,
                    platform=platform,
                    title=(title or content[:100])[:480],
                    content=(content or title)[:2000],
                    url=url[:990],
                    author=str(item.get("author", "Web"))[:180],
                    matched_keyword=str(item.get("matched_keyword", terms[0] if terms else system.name))[:180],
                    published_at=pub_dt,
                )
            )

        return mentions
