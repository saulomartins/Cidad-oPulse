from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector, CollectedMention, extract_search_terms

logger = logging.getLogger(__name__)


class YouTubeConnector(BaseConnector):
    id = "youtube"
    name = "YouTube Data API v3"
    category = "redes_sociais"
    description = "Monitora vídeos, reviews e reportagens no YouTube citando o sistema ou suas palavras-chave."
    requires_key = True
    env_var = "YOUTUBE_API_KEY"
    platforms = ["youtube"]

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 8,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        api_key = runtime_config.get("youtube_api_key", "")
        if not api_key:
            return []

        terms = extract_search_terms(system)[:2]
        published_after = (datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        mentions: list[CollectedMention] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for term in terms:
                try:
                    resp = await client.get(
                        "https://www.googleapis.com/youtube/v3/search",
                        params={
                            "part": "snippet",
                            "q": term,
                            "type": "video",
                            "order": "date",
                            "publishedAfter": published_after,
                            "maxResults": min(5, max_results),
                            "key": api_key,
                        },
                    )
                    if resp.status_code != 200:
                        continue
                    items = resp.json().get("items", [])
                    for item in items:
                        vid = item.get("id", {}).get("videoId")
                        if not vid or vid in seen:
                            continue
                        seen.add(vid)
                        snippet = item.get("snippet", {})
                        pub_str = snippet.get("publishedAt")
                        published_at = None
                        if pub_str:
                            try:
                                published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                            except ValueError:
                                published_at = datetime.now(timezone.utc)

                        mentions.append(
                            CollectedMention(
                                source_connector=self.id,
                                platform="youtube",
                                title=str(snippet.get("title", ""))[:480],
                                content=str(snippet.get("description", "") or snippet.get("title", ""))[:2000],
                                url=f"https://www.youtube.com/watch?v={vid}",
                                author=str(snippet.get("channelTitle", "YouTube"))[:180],
                                matched_keyword=term,
                                published_at=published_at,
                            )
                        )
                except Exception as exc:
                    logger.warning("YouTube API error for term %s: %s", term, exc)

        return mentions
