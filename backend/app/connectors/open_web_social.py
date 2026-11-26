from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.connectors.base import (
    BaseConnector,
    CollectedMention,
    infer_platform_from_url,
)
from app.services.relevance import (
    build_system_profile_tokens,
    evaluate_mention_quality,
    strip_html,
)

logger = logging.getLogger(__name__)


def _parse_relative_pt_date(label: str) -> datetime:
    """Parse Portuguese/English YouTube relative timestamps (e.g. 'há 7 meses', '3 weeks ago')."""
    now = datetime.now(timezone.utc)
    low = (label or "").lower()
    m = re.search(r"(\d+)\s*(minuto|hora|dia|semana|m[eê]s|ano|minute|hour|day|week|month|year)", low)
    if not m:
        return now
    qty = int(m.group(1))
    unit = m.group(2)
    if unit.startswith(("minuto", "minute")):
        return now - timedelta(minutes=qty)
    if unit.startswith(("hora", "hour")):
        return now - timedelta(hours=qty)
    if unit.startswith(("dia", "day")):
        return now - timedelta(days=qty)
    if unit.startswith(("semana", "week")):
        return now - timedelta(weeks=qty)
    if unit.startswith(("m", "month")):
        return now - timedelta(days=qty * 30)
    if unit.startswith(("ano", "year")):
        return now - timedelta(days=qty * 365)
    return now


async def _search_youtube_public(query: str, max_items: int = 8) -> list[dict[str, Any]]:
    """
    Fetch clean, direct YouTube video results from YouTube's public search page
    (no API key required, no search-engine snippet corruption).
    """
    if not query:
        return []
    results: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.youtube.com/results",
                params={"search_query": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "pt-BR,pt;q=0.9",
                },
            )
            if resp.status_code != 200:
                return []
            m = re.search(r"var ytInitialData = (\{.*?\});</script>", resp.text)
            if not m:
                return []
            data = json.loads(m.group(1))
            sections = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            seen_ids: set[str] = set()
            for sec in sections:
                for item in sec.get("itemSectionRenderer", {}).get("contents", []):
                    v = item.get("videoRenderer")
                    if not isinstance(v, dict):
                        continue
                    vid = str(v.get("videoId") or "").strip()
                    if not vid or vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    title = "".join(t.get("text", "") for t in v.get("title", {}).get("runs", [])).strip()
                    channel = "".join(t.get("text", "") for t in v.get("ownerText", {}).get("runs", [])).strip()
                    pub_label = str(v.get("publishedTimeText", {}).get("simpleText") or "")
                    snippets = [
                        "".join(r.get("text", "") for r in sn.get("snippetText", {}).get("runs", []))
                        for sn in (v.get("detailedMetadataSnippets") or [])
                    ]
                    desc = " ".join(s.strip() for s in snippets if s.strip())
                    results.append(
                        {
                            "title": strip_html(title),
                            "body": strip_html(desc or title),
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "author_override": channel or "YouTube",
                            "published_at": _parse_relative_pt_date(pub_label),
                            "matched_keyword": f"{query} (YouTube)",
                            "hint_platform": "youtube",
                        }
                    )
                    if len(results) >= max_items:
                        return results
    except Exception as exc:
        logger.warning("Direct YouTube public search failed (%s): %s", query[:80], exc)
    return results


def _timelimit_from_days(lookback_days: int) -> str | None:
    if lookback_days <= 7:
        return "w"
    if lookback_days <= 31:
        return "m"
    if lookback_days <= 366:
        return "y"
    return None


def _extract_author_from_url(url: str, platform: str) -> str:
    try:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if platform == "instagram" and parts and parts[0] not in {"p", "reel", "reels", "explore", "stories"}:
            return f"@{parts[0]}"
        if platform == "facebook" and parts and parts[0] not in {"posts", "watch", "photo", "share", "groups"}:
            return parts[0]
        if platform == "x" and parts and parts[0] not in {"i", "search", "hashtag"}:
            return f"@{parts[0]}"
        if platform == "youtube":
            return "YouTube"
        return parsed.netloc.replace("www.", "") or platform
    except Exception:
        return platform


def _parse_video_date(raw: Any) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _run_ddgs_queries_sync(
    queries: list[tuple[str, str, str]],
    video_query: str,
    primary_label: str,
    timelimit: str | None,
    per_query_limit: int = 5,
) -> list[dict[str, Any]]:
    """Run polite public web/social & video queries using DDGS synchronously inside a worker thread."""
    from ddgs import DDGS

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    with DDGS() as ddgs:
        # 1. Structured Video/Reel Search (returns clean YouTube + Instagram permalinks & real dates!)
        if video_query:
            try:
                vids = ddgs.videos(
                    video_query,
                    region="br-pt",
                    safesearch="moderate",
                    timelimit=timelimit,
                    max_results=8,
                )
                for v in vids or []:
                    href = str(v.get("content") or v.get("href") or "").strip()
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)
                    pub_name = str(v.get("uploader") or v.get("publisher") or "").strip()
                    results.append(
                        {
                            "title": strip_html(str(v.get("title") or "")),
                            "body": strip_html(str(v.get("description") or v.get("title") or "")),
                            "url": href,
                            "author_override": pub_name,
                            "published_at": _parse_video_date(v.get("published")),
                            "matched_keyword": f"{primary_label} (Vídeo/Reel)",
                            "hint_platform": infer_platform_from_url(href, default="youtube"),
                        }
                    )
            except Exception as exc:
                logger.warning("DDGS videos query failed (%s): %s", video_query[:80], exc)

        # 2. Public Web & Social text search
        for query_str, label, hint_platform in queries:
            try:
                rows = ddgs.text(
                    query_str,
                    region="br-pt",
                    safesearch="moderate",
                    timelimit=timelimit,
                    max_results=per_query_limit,
                )
                for r in rows or []:
                    href = str(r.get("href") or r.get("link") or "").strip()
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)
                    results.append(
                        {
                            "title": strip_html(str(r.get("title") or "")),
                            "body": strip_html(str(r.get("body") or r.get("snippet") or "")),
                            "url": href,
                            "matched_keyword": label,
                            "hint_platform": hint_platform,
                        }
                    )
            except Exception as exc:
                logger.warning("DDGS query failed (%s): %s", query_str[:80], exc)

    return results


class OpenWebSocialConnector(BaseConnector):
    id = "open_web_social"
    name = "Busca Aberta Redes Sociais & Web (Gratuito)"
    category = "redes_sociais"
    description = (
        "Varre posts, vídeos e páginas públicas no Instagram, Facebook, YouTube, X, LinkedIn, "
        "Reclame Aqui e web aberta gratuitamente (sem precisar de cartão ou API paga)."
    )
    requires_key = False
    env_var = ""
    platforms = ["instagram", "facebook", "youtube", "x", "linkedin", "reclame_aqui", "web"]

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 18,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        profile = build_system_profile_tokens(system)
        strong = profile["strong_phrases"][:2]
        short = profile["short_identity"][:1]
        identity_terms = strong or short or [system.name]

        # Build concise identity clause e.g. ("Diário Escolar Digital" OR "DED+")
        id_clause = (
            f"({' OR '.join(f'\"{t}\"' for t in identity_terms[:2])})"
            if len(identity_terms) > 1
            else f'"{identity_terms[0]}"'
        )
        geo_terms = profile.get("geo_terms", [])
        geo_anchor = ""
        if geo_terms:
            geo_parts = [f'"{g}"' if " " in g else g for g in geo_terms[:2]]
            geo_anchor = f" ({' OR '.join(geo_parts)})" if len(geo_parts) > 1 else f" {geo_parts[0]}"

        primary_label = identity_terms[0]
        # Avoid appending redundant geo_anchor if primary_label already includes state name/UF (e.g. "Minha Escola MG")
        primary_low = primary_label.lower()
        already_has_geo = any(g.lower() in primary_low for g in geo_terms if g)
        effective_geo = "" if already_has_geo else geo_anchor
        video_query = f"{primary_label} {geo_terms[0]}" if (geo_terms and not already_has_geo) else primary_label

        queries: list[tuple[str, str, str]] = [
            (f"site:instagram.com {id_clause}{effective_geo}", f"{primary_label} (Instagram)", "instagram"),
            (f"site:facebook.com {id_clause}{effective_geo}", f"{primary_label} (Facebook)", "facebook"),
            (f"site:youtube.com {id_clause}{effective_geo}", f"{primary_label} (YouTube)", "youtube"),
            (f'"{primary_label}"{effective_geo} (youtube OR instagram OR facebook)', f"{primary_label} (Redes Sociais)", "web"),
            (f"(site:x.com OR site:reclameaqui.com.br OR site:linkedin.com) {id_clause}{effective_geo}", f"{primary_label} (X/ReclameAqui/LinkedIn)", "web"),
            (f"{id_clause}{effective_geo} reclamação OR erro OR avaliação OR opinião", f"{primary_label} (Opiniões Web)", "web"),
        ]

        timelimit = _timelimit_from_days(lookback_days) if lookback_days <= 31 else None
        yt_rows, ddgs_rows = await asyncio.gather(
            _search_youtube_public(video_query, max_items=8),
            asyncio.to_thread(_run_ddgs_queries_sync, queries, video_query, primary_label, timelimit, 5),
        )
        seen_all: set[str] = set()
        raw_rows: list[dict[str, Any]] = []
        for row in yt_rows + ddgs_rows:
            u = row.get("url", "")
            if u and u not in seen_all:
                seen_all.add(u)
                raw_rows.append(row)

        mentions: list[CollectedMention] = []
        now = datetime.now(timezone.utc)
        for row in raw_rows:
            if len(mentions) >= max_results:
                break
            url = row["url"]
            platform = infer_platform_from_url(url, default=row["hint_platform"])
            author = row.get("author_override") or _extract_author_from_url(url, platform)
            title = row["title"] or f"Publicação sobre {system.name}"
            content = row["body"] or title
            content_type = "post" if platform in {"instagram", "facebook", "x", "linkedin", "youtube"} else "mention"
            pub_dt = row.get("published_at") or now

            ok_quality, quality_reason = evaluate_mention_quality(
                source_connector=self.id,
                platform=platform,
                content_type=content_type,
                title=title,
                content=content,
                url=url,
                system=system,
            )
            if not ok_quality:
                logger.info("Skipped low-trust web search result (%s): %s", url[:80], quality_reason)
                continue

            mentions.append(
                CollectedMention(
                    source_connector=self.id,
                    platform=platform,
                    content_type=content_type,
                    parent_post_url=url if content_type == "post" else "",
                    title=title[:480],
                    content=content[:2000],
                    url=url[:990],
                    author=author[:180],
                    matched_keyword=row["matched_keyword"][:180],
                    published_at=pub_dt,
                )
            )

        return mentions
