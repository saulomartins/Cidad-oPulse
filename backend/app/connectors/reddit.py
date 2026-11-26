from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.connectors.base import BaseConnector, CollectedMention
from app.services.relevance import build_contextual_search_queries

logger = logging.getLogger(__name__)


class RedditPublicConnector(BaseConnector):
    id = "reddit"
    name = "Reddit Busca Pública"
    category = "comunidades_sociais"
    description = "Monitora discussões, dúvidas e reclamações em comunidades do Reddit sem necessidade de chave de API."
    requires_key = False
    env_var = ""
    platforms = ["reddit"]

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 10,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        queries = build_contextual_search_queries(system, max_queries=3)
        if not queries:
            return []

        t_param = "week" if lookback_days <= 7 else ("month" if lookback_days <= 31 else ("year" if lookback_days <= 366 else "all"))
        mentions: list[CollectedMention] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for query_str, label in queries:
                url = f"https://www.reddit.com/search.json?q={quote_plus(query_str)}&sort=new&t={t_param}&limit=6"
                try:
                    resp = await client.get(
                        url,
                        headers={"User-Agent": "CidadaoPulse/1.0 (civic sentiment monitor)"},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    children = data.get("data", {}).get("children", [])
                    for child in children:
                        post = child.get("data", {})
                        permalink = post.get("permalink", "")
                        full_url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")
                        if not full_url or full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        created_utc = post.get("created_utc")
                        published_at = (
                            datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else None
                        )
                        title = str(post.get("title", "")).strip()
                        selftext = str(post.get("selftext", "")).strip()
                        subreddit = post.get("subreddit_name_prefixed", "r/reddit")
                        author = f"u/{post.get('author', 'anon')} ({subreddit})"

                        mentions.append(
                            CollectedMention(
                                source_connector=self.id,
                                platform="reddit",
                                title=title[:480],
                                content=(selftext or title)[:2000],
                                url=full_url[:990],
                                author=author[:180],
                                matched_keyword=label,
                                published_at=published_at,
                            )
                        )
                        if len(mentions) >= max_results:
                            return mentions
                except Exception as exc:
                    logger.warning("Reddit search error for query %s: %s", query_str, exc)

        return mentions
