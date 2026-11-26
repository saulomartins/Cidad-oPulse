from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse


@dataclass
class CollectedMention:
    source_connector: str
    platform: str
    title: str
    content: str
    url: str
    author: str = ""
    matched_keyword: str = ""
    published_at: datetime | None = None
    content_type: str = "mention"  # mention | post | comment
    parent_post_url: str = ""
    bypass_relevance: bool = False  # True for comments extracted directly from a user-supplied post about the system
    extra: dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        norm_url = self.url.strip().lower()
        norm_text = (self.title.strip() + " " + self.content.strip())[:300].lower()
        if self.content_type == "comment":
            # Multiple comments share the same parent post URL, so hash author + text + parent URL
            key = f"comment|{self.parent_post_url.strip().lower() or norm_url}|{self.author.strip().lower()}|{norm_text}"
        else:
            key = norm_url if norm_url and not norm_url.startswith("#") else norm_text
        return hashlib.sha256(key.encode("utf-8", errors="ignore")).hexdigest()


def extract_search_terms(system) -> list[str]:
    """Build prioritized search terms from keywords, system name, and domain URLs."""
    terms: list[str] = []
    try:
        keywords = json.loads(system.keywords_json or "[]")
    except json.JSONDecodeError:
        keywords = []
    try:
        urls = json.loads(system.urls_json or "[]")
    except json.JSONDecodeError:
        urls = []

    for kw in keywords:
        cleaned = str(kw).strip()
        if cleaned and cleaned not in terms:
            terms.append(cleaned)

    if system.name and system.name.strip() not in terms:
        terms.insert(0, system.name.strip())

    for raw_url in urls:
        parsed = urlparse(str(raw_url).strip())
        host = (parsed.netloc or parsed.path).replace("www.", "").strip("/")
        if host and host not in terms:
            terms.append(host)

    return terms[:8]


def infer_platform_from_url(url: str, default: str = "web") -> str:
    lower = (url or "").lower()
    if "twitter.com" in lower or "x.com" in lower:
        return "x"
    if "instagram.com" in lower:
        return "instagram"
    if "facebook.com" in lower or "fb.com" in lower:
        return "facebook"
    if "linkedin.com" in lower:
        return "linkedin"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    if "tiktok.com" in lower:
        return "tiktok"
    if "reddit.com" in lower:
        return "reddit"
    if "reclameaqui.com" in lower:
        return "reclame_aqui"
    if "play.google.com" in lower or "apps.apple.com" in lower:
        return "app_store"
    if "news.google.com" in lower or "g1.globo" in lower or "uol.com" in lower or "folha" in lower:
        return "news"
    return default


class BaseConnector(ABC):
    id: str = "base"
    name: str = "Base Connector"
    category: str = "web"
    description: str = ""
    requires_key: bool = False
    env_var: str = ""
    platforms: list[str] = ["web"]

    def is_configured(self, runtime_config: dict[str, Any]) -> bool:
        if not self.requires_key:
            return True
        return bool(runtime_config.get(self.env_var.lower(), ""))

    @abstractmethod
    async def collect(
        self,
        system,
        runtime_config: dict[str, Any],
        max_results: int = 15,
        lookback_days: int = 365,
    ) -> list[CollectedMention]:
        raise NotImplementedError
