from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector, CollectedMention, extract_search_terms
from app.services.relevance import (
    evaluate_comment_relevance,
    evaluate_mention_relevance,
    normalize_text,
)

logger = logging.getLogger(__name__)


def _is_valid_social_profile(entry: str) -> bool:
    """Only accept real @handles or Instagram/Facebook profile/page URLs."""
    s = (entry or "").strip()
    if not s or " " in s or len(s) > 180:
        return False
    if re.fullmatch(r"@[A-Za-z0-9._]{3,40}", s):
        return True
    low = s.lower()
    if low.startswith(("http://", "https://")) and any(
        dom in low for dom in ("instagram.com/", "facebook.com/", "fb.com/")
    ):
        return True
    return False


def extract_social_profiles(system) -> list[str]:
    """
    Extract valid Instagram/Facebook @handles and page URLs from social_profiles_json,
    AND always merge any @handles or social URLs found inside keywords_json / urls_json.
    """
    profiles: list[str] = []

    def add_profile(candidate: str) -> None:
        cleaned = (candidate or "").strip().rstrip(",")
        if _is_valid_social_profile(cleaned) and cleaned not in profiles:
            profiles.append(cleaned)

    try:
        raw = json.loads(getattr(system, "social_profiles_json", "[]") or "[]")
        for p in raw:
            p_str = str(p).strip()
            if _is_valid_social_profile(p_str):
                add_profile(p_str)
            else:
                # Extract any @handles or social URLs embedded inside free text
                for handle in re.findall(r"@[A-Za-z0-9._]{3,40}", p_str):
                    add_profile(handle)
                for url in re.findall(r"https?://(?:www\.)?(?:instagram\.com|facebook\.com|fb\.com)/\S+", p_str):
                    add_profile(url)
    except json.JSONDecodeError:
        pass

    # Always also extract @handles from keywords_json (users frequently put @educacaomg there)
    try:
        kws = json.loads(system.keywords_json or "[]")
        for kw in kws:
            for handle in re.findall(r"@[A-Za-z0-9._]{3,40}", str(kw)):
                add_profile(handle)
    except json.JSONDecodeError:
        pass

    # Also inspect urls_json for explicit Instagram/Facebook page URLs
    try:
        urls = json.loads(system.urls_json or "[]")
        for u in urls:
            add_profile(str(u))
    except json.JSONDecodeError:
        pass

    return profiles[:8]


def extract_clean_hashtags(system) -> list[str]:
    """Extract valid alphanumeric Instagram hashtags (no spaces, '+' or punctuation)."""
    tags: list[str] = []
    try:
        kws = json.loads(system.keywords_json or "[]")
    except json.JSONDecodeError:
        kws = []

    # 1. Explicit #hashtags from keywords (prioritize distinctive ones, skip overly generic ones)
    generic_tags = {"educacao", "escolapublica", "educacaopublica", "governo", "brasil"}
    for kw in kws:
        for raw_tag in re.findall(r"#([A-Za-zÀ-ÿ0-9_+]+)", str(kw)):
            norm = normalize_text(raw_tag).replace("+", "mais")
            clean = re.sub(r"[^a-z0-9]", "", norm)
            if 4 <= len(clean) <= 32 and clean not in generic_tags and clean not in tags:
                tags.append(clean)

    # 2. Fallback from primary brand terms if no explicit hashtags
    if not tags:
        for term in extract_search_terms(system)[:3]:
            norm = normalize_text(term).replace("+", "mais")
            clean = re.sub(r"[^a-z0-9]", "", norm)
            if 4 <= len(clean) <= 32 and clean not in tags:
                tags.append(clean)

    return tags[:4]


def _parse_iso_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


class XApiConnector(BaseConnector):
    id = "x_api"
    name = "X (Twitter) API v2"
    category = "redes_sociais_plugaveis"
    description = "Conector oficial para buscas recentes no X/Twitter via Bearer Token (API v2)."
    requires_key = True
    env_var = "X_BEARER_TOKEN"
    platforms = ["x"]

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 10,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        token = runtime_config.get("x_bearer_token", "")
        if not token:
            return []

        terms = extract_search_terms(system)[:3]
        if not terms:
            return []

        query = " OR ".join(f'"{t}"' if " " in t else t for t in terms) + " -is:retweet"
        mentions: list[CollectedMention] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    params={
                        "query": query[:500],
                        "max_results": max(10, min(max_results, 25)),
                        "tweet.fields": "created_at,author_id",
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("X API returned %s: %s", resp.status_code, resp.text[:200])
                    return []
                for tweet in resp.json().get("data", [])[:max_results]:
                    tid = tweet.get("id", "")
                    text = str(tweet.get("text", "")).strip()
                    mentions.append(
                        CollectedMention(
                            source_connector=self.id,
                            platform="x",
                            content_type="post",
                            title=text[:140],
                            content=text[:2000],
                            url=f"https://x.com/i/web/status/{tid}" if tid else "",
                            author=f"user:{tweet.get('author_id', 'x')}",
                            matched_keyword=terms[0],
                            published_at=_parse_iso_dt(tweet.get("created_at")),
                        )
                    )
            except Exception as exc:
                logger.warning("X API error: %s", exc)

        return mentions


class ApifySocialConnector(BaseConnector):
    id = "apify_social"
    name = "Apify (Instagram / Facebook Posts & Comentários)"
    category = "redes_sociais_plugaveis"
    description = (
        "Coleta posts públicos e COMENTÁRIOS no Instagram e Facebook (por perfis públicos como @educacaomg, "
        "hashtags ou URLs de posts específicos) sem precisar ser administrador da página. Ative com APIFY_TOKEN."
    )
    requires_key = True
    env_var = "APIFY_TOKEN"
    platforms = ["instagram", "facebook", "tiktok"]

    def _collect_ig_post_and_comments(
        self,
        post: dict[str, Any],
        system,
        matched_label: str,
        out: list[CollectedMention],
    ) -> None:
        caption = str(post.get("caption") or "").strip()
        post_url = str(post.get("url") or "")
        owner = str(post.get("ownerUsername") or "instagram")
        pub_dt = _parse_iso_dt(post.get("timestamp"))

        post_is_rel, _, _ = evaluate_mention_relevance(
            system, title=caption[:160], content=caption, url=post_url, matched_keyword=matched_label
        )
        if post_is_rel and (caption or post_url):
            out.append(
                CollectedMention(
                    source_connector=self.id,
                    platform="instagram",
                    content_type="post",
                    title=(caption[:140] or f"Post de @{owner}"),
                    content=caption[:2000],
                    url=post_url[:990],
                    parent_post_url=post_url[:990],
                    author=f"@{owner}",
                    matched_keyword=matched_label,
                    published_at=pub_dt,
                )
            )

        # Inspect comments: if post is about system -> keep ALL comments;
        # otherwise STILL keep any comment that explicitly mentions the system!
        for c in (post.get("latestComments") or [])[:20]:
            ctext = str(c.get("text") or "").strip()
            if not ctext:
                continue
            ok_comment, _ = evaluate_comment_relevance(system, ctext)
            if not ok_comment:
                continue
            cuser = str(c.get("ownerUsername") or "usuario_ig")
            if not post_is_rel:
                c_rel, _, _ = evaluate_mention_relevance(
                    system, title=ctext[:140], content=f"{ctext} {owner}", url=post_url
                )
                if not c_rel:
                    continue
            out.append(
                CollectedMention(
                    source_connector=self.id,
                    platform="instagram",
                    content_type="comment",
                    title=f"Comentário de @{cuser} em @{owner}",
                    content=ctext[:2000],
                    url=post_url[:990],
                    parent_post_url=post_url[:990],
                    author=f"@{cuser}",
                    matched_keyword=f"Comentário Instagram ({system.name})",
                    published_at=_parse_iso_dt(c.get("timestamp") or post.get("timestamp")),
                    bypass_relevance=True,
                )
            )

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 20,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        token = runtime_config.get("apify_token", "")
        if not token:
            return []

        headers = {"Authorization": f"Bearer {token}"}
        mentions: list[CollectedMention] = []
        profiles = extract_social_profiles(system)
        clean_hashtags = extract_clean_hashtags(system)

        async with httpx.AsyncClient(timeout=90.0, headers=headers) as client:
            ig_urls: list[str] = []
            fb_urls: list[str] = []
            for p in profiles:
                low = p.lower()
                if "facebook.com" in low or "fb.com" in low:
                    fb_urls.append(p)
                elif "instagram.com" in low:
                    ig_urls.append(p)
                elif p.startswith("@"):
                    ig_urls.append(f"https://www.instagram.com/{p.lstrip('@')}/")

            # 1. Monitor public Instagram profiles -> posts + comments
            if ig_urls:
                try:
                    resp = await client.post(
                        "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items",
                        params={"limit": 45},
                        json={
                            "directUrls": ig_urls[:4],
                            "resultsType": "posts",
                            "resultsLimit": 25,
                            "addParentData": False,
                        },
                    )
                    if resp.status_code in (200, 201) and isinstance(resp.json(), list):
                        for post in resp.json():
                            self._collect_ig_post_and_comments(post, system, system.name, mentions)
                    else:
                        logger.warning("Apify IG profile scraper returned %s: %s", resp.status_code, resp.text[:200])
                except Exception as exc:
                    logger.warning("Apify Instagram profile/comments error: %s", exc)

            # 2. Monitor Instagram hashtags (sanitized alphanumeric hashtags like #diarioescolardigital, #dedmais)
            if clean_hashtags:
                try:
                    resp = await client.post(
                        "https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items",
                        params={"limit": 20},
                        json={
                            "hashtags": clean_hashtags[:3],
                            "resultsLimit": 12,
                        },
                    )
                    if resp.status_code in (200, 201) and isinstance(resp.json(), list):
                        for post in resp.json():
                            self._collect_ig_post_and_comments(
                                post, system, f"#{clean_hashtags[0]}", mentions
                            )
                    else:
                        logger.warning("Apify IG hashtag scraper returned %s: %s", resp.status_code, resp.text[:200])
                except Exception as exc:
                    logger.warning("Apify hashtag scraper error: %s", exc)

            # 2b. Pull comments automatically for top discovered relevant Instagram posts that lacked inline comments
            ig_posts_needing_comments = [
                m.url
                for m in mentions
                if m.platform == "instagram" and m.content_type == "post" and m.url
            ]
            posts_with_comments = {
                m.parent_post_url
                for m in mentions
                if m.platform == "instagram" and m.content_type == "comment" and m.parent_post_url
            }
            for post_url in list(dict.fromkeys(ig_posts_needing_comments))[:3]:
                if post_url not in posts_with_comments:
                    extra_comments = await self.collect_comments_from_post_url(
                        post_url, system, runtime_config, max_comments=25
                    )
                    mentions.extend(extra_comments)

            # 3. Monitor public Facebook pages -> relevant posts + comments
            if fb_urls:
                try:
                    resp = await client.post(
                        "https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items",
                        params={"limit": 12},
                        json={"startUrls": [{"url": u} for u in fb_urls[:2]], "resultsLimit": 10},
                    )
                    if resp.status_code in (200, 201) and isinstance(resp.json(), list):
                        for post in resp.json():
                            text = str(post.get("text") or "").strip()
                            post_url = str(post.get("url") or post.get("topLevelUrl") or "")
                            page_name = str(post.get("pageName") or "Facebook")
                            is_rel, _, _ = evaluate_mention_relevance(
                                system, title=text[:160], content=text, url=post_url
                            )
                            if not is_rel:
                                continue
                            mentions.append(
                                CollectedMention(
                                    source_connector=self.id,
                                    platform="facebook",
                                    content_type="post",
                                    title=text[:140] or f"Post em {page_name}",
                                    content=text[:2000],
                                    url=post_url[:990],
                                    parent_post_url=post_url[:990],
                                    author=page_name[:180],
                                    matched_keyword=system.name,
                                    published_at=_parse_iso_dt(post.get("time")),
                                )
                            )
                            if post_url:
                                fb_comments = await self.collect_comments_from_post_url(
                                    post_url, system, runtime_config, max_comments=15
                                )
                                mentions.extend(fb_comments)
                except Exception as exc:
                    logger.warning("Apify Facebook page error: %s", exc)

        return mentions[: max_results * 3]

    async def collect_comments_from_post_url(
        self,
        post_url: str,
        system,
        runtime_config: dict[str, Any],
        max_comments: int = 50,
    ) -> list[CollectedMention]:
        """Extract public comments directly from a specific Instagram or Facebook post URL via Apify."""
        token = runtime_config.get("apify_token", "")
        if not token or not post_url:
            return []

        low = post_url.lower()
        is_fb = "facebook.com" in low or "fb.com" in low or "fb.watch" in low
        is_ig = "instagram.com" in low
        if not (is_fb or is_ig):
            return []

        headers = {"Authorization": f"Bearer {token}"}
        mentions: list[CollectedMention] = []
        async with httpx.AsyncClient(timeout=90.0, headers=headers) as client:
            try:
                if is_ig:
                    endpoint = "https://api.apify.com/v2/acts/apify~instagram-comment-scraper/run-sync-get-dataset-items"
                    payload = {"directUrls": [post_url], "resultsLimit": max_comments}
                    platform = "instagram"
                else:
                    endpoint = "https://api.apify.com/v2/acts/apify~facebook-comments-scraper/run-sync-get-dataset-items"
                    payload = {"startUrls": [{"url": post_url}], "resultsLimit": max_comments}
                    platform = "facebook"

                resp = await client.post(endpoint, params={"limit": max_comments}, json=payload)
                if resp.status_code not in (200, 201) or not isinstance(resp.json(), list):
                    logger.warning("Apify comments scraper returned %s: %s", resp.status_code, resp.text[:200])
                    return []

                for item in resp.json()[:max_comments]:
                    text = str(item.get("text") or item.get("comment") or "").strip()
                    if not text:
                        continue
                    ok_comment, _ = evaluate_comment_relevance(system, text)
                    if not ok_comment:
                        continue
                    author = str(
                        item.get("ownerUsername")
                        or item.get("profileName")
                        or item.get("author")
                        or f"usuario_{platform}"
                    )
                    comment_url = str(item.get("commentUrl") or item.get("postUrl") or post_url)
                    mentions.append(
                        CollectedMention(
                            source_connector=self.id,
                            platform=platform,
                            content_type="comment",
                            title=f"Comentário de {author} ({platform.upper()})",
                            content=text[:2000],
                            url=comment_url[:990],
                            parent_post_url=post_url[:990],
                            author=author[:180],
                            matched_keyword=f"Comentário no post ({system.name})",
                            published_at=_parse_iso_dt(item.get("timestamp") or item.get("date")),
                            bypass_relevance=True,
                        )
                    )
            except Exception as exc:
                logger.warning("Apify post comments error (%s): %s", post_url, exc)

        return mentions


class MetaGraphConnector(BaseConnector):
    id = "meta_api"
    name = "Meta Graph API (Instagram & Facebook Oficial)"
    category = "redes_sociais_plugaveis"
    description = (
        "Conector oficial da Meta Graph API para coletar menções, posts e TODOS os comentários "
        "das páginas do Facebook e contas Instagram Business que vocês administram."
    )
    requires_key = True
    env_var = "META_ACCESS_TOKEN"
    platforms = ["facebook", "instagram"]

    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 20,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        token = runtime_config.get("meta_access_token", "")
        if not token:
            return []

        mentions: list[CollectedMention] = []
        fields = (
            "id,name,"
            "tagged.limit(10){message,permalink_url,created_time,from},"
            "posts.limit(12){message,permalink_url,created_time,"
            "comments.limit(30){message,from,created_time,permalink_url}},"
            "instagram_business_account{id,username,"
            "media.limit(12){caption,permalink,timestamp,"
            "comments.limit(30){text,username,timestamp}}}"
        )

        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                resp = await client.get(
                    "https://graph.facebook.com/v21.0/me/accounts",
                    params={"access_token": token, "fields": fields},
                )
                if resp.status_code != 200:
                    logger.warning("Meta Graph API returned %s: %s", resp.status_code, resp.text[:200])
                    return []

                for page in resp.json().get("data", []):
                    page_name = str(page.get("name", "Facebook"))

                    # 1. Facebook tagged mentions
                    for post in page.get("tagged", {}).get("data", []):
                        msg = str(post.get("message", "")).strip()
                        if not msg:
                            continue
                        mentions.append(
                            CollectedMention(
                                source_connector=self.id,
                                platform="facebook",
                                content_type="mention",
                                title=msg[:140],
                                content=msg[:2000],
                                url=str(post.get("permalink_url", ""))[:990],
                                author=str(post.get("from", {}).get("name", page_name))[:180],
                                matched_keyword=system.name,
                                published_at=_parse_iso_dt(post.get("created_time")),
                            )
                        )

                    # 2. Facebook Page posts + comments
                    for post in page.get("posts", {}).get("data", []):
                        post_msg = str(post.get("message", "")).strip()
                        post_url = str(post.get("permalink_url", ""))
                        post_is_about_system, _, _ = evaluate_mention_relevance(
                            system, title=post_msg[:160], content=post_msg, url=post_url
                        )
                        for c in post.get("comments", {}).get("data", []):
                            cmsg = str(c.get("message", "")).strip()
                            if not cmsg:
                                continue
                            c_author = str(c.get("from", {}).get("name", "Cidadão (Facebook)"))
                            c_url = str(c.get("permalink_url") or post_url)
                            mentions.append(
                                CollectedMention(
                                    source_connector=self.id,
                                    platform="facebook",
                                    content_type="comment",
                                    title=f"Comentário de {c_author} em {page_name}",
                                    content=cmsg[:2000],
                                    url=c_url[:990],
                                    parent_post_url=post_url[:990],
                                    author=c_author[:180],
                                    matched_keyword=f"Comentário Facebook ({system.name})",
                                    published_at=_parse_iso_dt(c.get("created_time")),
                                    bypass_relevance=post_is_about_system,
                                )
                            )

                    # 3. Linked Instagram Business Account media + comments
                    ig = page.get("instagram_business_account") or {}
                    ig_user = str(ig.get("username", "instagram"))
                    for media in ig.get("media", {}).get("data", []):
                        caption = str(media.get("caption", "")).strip()
                        permalink = str(media.get("permalink", ""))
                        post_is_about_system, _, _ = evaluate_mention_relevance(
                            system, title=caption[:160], content=caption, url=permalink
                        )
                        for c in media.get("comments", {}).get("data", []):
                            ctext = str(c.get("text", "")).strip()
                            if not ctext:
                                continue
                            c_user = str(c.get("username", "usuario_ig"))
                            mentions.append(
                                CollectedMention(
                                    source_connector=self.id,
                                    platform="instagram",
                                    content_type="comment",
                                    title=f"Comentário de @{c_user} em @{ig_user}",
                                    content=ctext[:2000],
                                    url=permalink[:990],
                                    parent_post_url=permalink[:990],
                                    author=f"@{c_user}",
                                    matched_keyword=f"Comentário Instagram ({system.name})",
                                    published_at=_parse_iso_dt(c.get("timestamp")),
                                    bypass_relevance=post_is_about_system,
                                )
                            )
            except Exception as exc:
                logger.warning("Meta Graph API error: %s", exc)

        return mentions[: max_results * 2]
