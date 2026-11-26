from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector
from app.connectors.gemini_web import GeminiWebSearchConnector
from app.connectors.google_news import GoogleNewsRSSConnector
from app.connectors.open_web_social import OpenWebSocialConnector
from app.connectors.reddit import RedditPublicConnector
from app.connectors.social_paid import ApifySocialConnector, MetaGraphConnector, XApiConnector
from app.connectors.youtube import YouTubeConnector


ALL_CONNECTORS: list[BaseConnector] = [
    OpenWebSocialConnector(),
    GoogleNewsRSSConnector(),
    RedditPublicConnector(),
    GeminiWebSearchConnector(),
    YouTubeConnector(),
    ApifySocialConnector(),
    XApiConnector(),
    MetaGraphConnector(),
]


def get_connector_registry() -> dict[str, BaseConnector]:
    return {c.id: c for c in ALL_CONNECTORS}


def list_connector_statuses(runtime_config: dict[str, Any]) -> list[dict[str, Any]]:
    statuses = []
    for connector in ALL_CONNECTORS:
        configured = connector.is_configured(runtime_config)
        statuses.append(
            {
                "id": connector.id,
                "name": connector.name,
                "category": connector.category,
                "description": connector.description,
                "enabled": configured,
                "requires_key": connector.requires_key,
                "configured": configured,
                "env_var": connector.env_var,
                "platforms": connector.platforms,
            }
        )
    return statuses
