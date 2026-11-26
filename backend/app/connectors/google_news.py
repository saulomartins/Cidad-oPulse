from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx

from app.connectors.base import BaseConnector, CollectedMention
from app.services.relevance import build_contextual_search_queries, strip_html

logger = logging.getLogger(__name__)


class GoogleNewsRSSConnector(BaseConnector):
    id = "google_news"
    name = "Google News RSS"
    category = "notícias_abertas"
    description = "Coleta notícias e artigos públicos na internet via Google News RSS (PT-BR e internacional) com queries contextuais sem precisar de chave de API."
    requires_key = False
    env_var = ""
    platforms = ["news", "web"]

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 12,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        queries = build_contextual_search_queries(system, max_queries=4)
        if not queries:
            return []

        mentions: list[CollectedMention] = []
        seen_urls: set[str] = set()
        when_clause = f"when:{max(1, min(730, int(lookback_days)))}d"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for query_str, label in queries:
                rss_url = (
                    f"https://news.google.com/rss/search?"
                    f"q={quote_plus(query_str + ' ' + when_clause)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
                )
                try:
                    resp = await client.get(
                        rss_url,
                        headers={"User-Agent": "CidadaoPulseMonitor/1.0 (+https://localhost)"},
                    )
                    if resp.status_code != 200:
                        continue
                    parsed = feedparser.parse(resp.text)
                    per_query = max(4, max_results // max(1, len(queries)))
                    for entry in parsed.entries[:per_query]:
                        link = getattr(entry, "link", "") or ""
                        if not link or link in seen_urls:
                            continue
                        seen_urls.add(link)

                        published_at = None
                        raw_date = getattr(entry, "published", None)
                        if raw_date:
                            try:
                                published_at = parsedate_to_datetime(raw_date).astimezone(timezone.utc)
                            except Exception:
                                published_at = datetime.now(timezone.utc)

                        source_obj = getattr(entry, "source", None)
                        author = getattr(source_obj, "title", "") if source_obj else "Google News"
                        title = strip_html(getattr(entry, "title", ""))
                        summary = strip_html(getattr(entry, "summary", ""))

                        mentions.append(
                            CollectedMention(
                                source_connector=self.id,
                                platform="news",
                                title=title[:480],
                                content=(summary or title)[:2000],
                                url=link[:990],
                                author=author[:180],
                                matched_keyword=label,
                                published_at=published_at,
                            )
                        )
                        if len(mentions) >= max_results:
                            return mentions
                except Exception as exc:
                    logger.warning("GoogleNewsRSS error for query %s: %s", query_str, exc)

        return mentions
