from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ============================================================
# Monitored Systems
# ============================================================
class SystemBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str = Field(default="", description="Descrição completa do que o sistema faz para o cidadão")
    urls: list[str] = Field(default_factory=list, description="URLs oficiais, portais ou links de apps")
    keywords: list[str] = Field(default_factory=list, description="Palavras-chave, hashtags, arrobas ou nomes alternativos")
    social_profiles: list[str] = Field(default_factory=list, description="Perfis públicos ou páginas IG/FB monitoradas (ex: @educacaomg, https://facebook.com/...)")
    stage: Literal["iniciativa", "producao"] = "iniciativa"
    uses_ai: Literal["com_ia", "sem_ia", "hibrido"] = "sem_ia"
    ai_details: str = ""
    citizen_area: str = "Serviços Públicos Digitais"
    target_audience: str = "Cidadãos em geral"
    organization_type: str = "Governo Municipal"
    country: str = "Brasil"
    state_uf: str = ""
    municipality: str = ""
    impact_summary: str = ""
    monitor_sentiment: bool = True
    monitor_awards: bool = True
    is_active: bool = True


class SystemCreate(SystemBase):
    pass


class SystemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    urls: list[str] | None = None
    keywords: list[str] | None = None
    social_profiles: list[str] | None = None
    stage: Literal["iniciativa", "producao"] | None = None
    uses_ai: Literal["com_ia", "sem_ia", "hibrido"] | None = None
    ai_details: str | None = None
    citizen_area: str | None = None
    target_audience: str | None = None
    organization_type: str | None = None
    country: str | None = None
    state_uf: str | None = None
    municipality: str | None = None
    impact_summary: str | None = None
    monitor_sentiment: bool | None = None
    monitor_awards: bool | None = None
    is_active: bool | None = None


class SystemOut(SystemBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    mentions_count: int = 0
    avg_sentiment: float = 0.0
    awards_count: int = 0


# ============================================================
# Mentions & Sentiment
# ============================================================
class MentionOut(BaseModel):
    id: int
    system_id: int
    system_name: str = ""
    source_connector: str
    platform: str
    content_type: str = "mention"
    parent_post_url: str = ""
    title: str
    content: str
    url: str
    author: str
    matched_keyword: str
    published_at: datetime | None = None
    sentiment: Literal["positivo", "neutro", "negativo"]
    sentiment_score: float
    confidence: float
    topics: list[str] = Field(default_factory=list)
    summary: str
    sentiment_reason: str = ""
    evidence_quote: str = ""
    is_crisis_signal: bool
    analyzed_by: str
    collected_at: datetime


class SentimentTrendPoint(BaseModel):
    date: str
    positivo: int
    neutro: int
    negativo: int
    avg_score: float


class SentimentOverview(BaseModel):
    total_mentions: int
    positive_count: int
    neutral_count: int
    negative_count: int
    crisis_count: int
    avg_score: float
    sentiment_index: int  # 0..100
    by_platform: list[dict]
    top_topics: list[dict]
    trend: list[SentimentTrendPoint]


class ScanRequest(BaseModel):
    system_id: int | None = None
    connectors: list[str] | None = None
    lookback_days: int | None = Field(default=365, ge=1, le=730)


class TemporalWindowSummary(BaseModel):
    days: int
    label: str
    total_mentions: int
    positive_count: int
    neutral_count: int
    negative_count: int
    crisis_count: int
    avg_score: float
    sentiment_index: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float


class TemporalSeriesPoint(BaseModel):
    bucket: str
    label: str
    positivo: int
    neutro: int
    negativo: int
    total: int
    avg_score: float
    sentiment_index: int | None = None


class ChannelGroupSummary(BaseModel):
    group: str  # redes_sociais | internet
    label: str
    total_mentions: int
    positive_count: int
    neutral_count: int
    negative_count: int
    sentiment_index: int
    platforms: list[dict]


class TemporalAnalysisOut(BaseModel):
    system_id: int | None
    system_name: str
    period_days: int
    period_label: str
    granularity: Literal["day", "month"]
    date_from: str
    date_to: str
    current: TemporalWindowSummary
    previous: TemporalWindowSummary
    mentions_delta: int
    sentiment_index_delta: int
    trend_direction: Literal["melhorando", "piorando", "estavel", "sem_dados"]
    narrative_summary: str
    windows_summary: list[TemporalWindowSummary]
    series: list[TemporalSeriesPoint]
    channel_groups: list[ChannelGroupSummary]
    top_topics: list[dict]


class ImportCommentsRequest(BaseModel):
    system_id: int
    platform: Literal["instagram", "facebook", "youtube", "x", "reclame_aqui", "web"] = "instagram"
    post_url: str = ""
    raw_text: str = Field(..., min_length=3, description="Um comentário por linha, ou formato 'Autor | Comentário', ou CSV")


class FetchPostCommentsRequest(BaseModel):
    system_id: int
    post_url: str = Field(..., min_length=10)
    max_comments: int = Field(default=50, ge=5, le=200)


class ProblemEvidenceOut(BaseModel):
    id: int
    system_name: str
    platform: str
    content_type: str
    author: str
    title: str
    excerpt: str
    url: str
    sentiment: str
    sentiment_score: float
    is_crisis_signal: bool
    date: str


class ProblemClusterOut(BaseModel):
    id: str
    title: str
    category: str
    severity: Literal["critica", "alta", "media", "baixa"]
    action_type: Literal["tecnica", "ux", "comunicacao", "suporte"]
    mentions_count: int
    share_pct: float
    avg_sentiment: float
    trend: Literal["subindo", "caindo", "estavel", "novo"]
    platforms: list[dict]
    description: str
    recommended_action: str
    evidences: list[ProblemEvidenceOut]


class ProblemDiagnosticsOut(BaseModel):
    system_id: int | None
    system_name: str
    days: int | None
    channel_group: str
    total_mentions_analyzed: int
    total_comments_analyzed: int
    total_friction_mentions: int
    problems_count: int
    critical_or_high_count: int
    top_complaint_channel: str
    analyzed_by: str
    executive_summary: str
    problems: list[ProblemClusterOut]


# ============================================================
# Awards & Contests Radar
# ============================================================
class AwardOut(BaseModel):
    id: int
    system_id: int
    system_name: str = ""
    title: str
    organizer: str
    description: str
    official_url: str
    scope: str
    country_region: str
    country: str = ""
    city: str = ""
    latitude: float | None = None
    longitude: float | None = None
    ai_requirement: str
    stage_eligibility: str
    deadline: str
    deadline_date: str = ""
    days_remaining: int | None = None
    is_open_for_application: bool = True
    award_status: str
    deadline_verified_at: datetime | None = None
    deadline_source_note: str = ""
    prize_benefits: str
    categories: list[str] = Field(default_factory=list)
    match_score: int
    match_reasoning: str
    next_steps: str
    discovery_source: str
    pipeline_status: str
    user_notes: str
    discovered_at: datetime
    updated_at: datetime


class AwardPipelineUpdate(BaseModel):
    pipeline_status: Literal["novo", "analisando", "inscrito", "premiado", "descartado"] | None = None
    user_notes: str | None = None
    award_status: Literal["aberto", "previsto", "recorrente", "encerrado"] | None = None
    deadline: str | None = None
    deadline_date: str | None = None
    deadline_source_note: str | None = None


class AwardsScanRequest(BaseModel):
    system_id: int | None = None
    focus_scope: Literal["todos", "internacional", "nacional"] = "todos"
    include_ai_filter: Literal["auto", "com_ia", "sem_ia", "ambos"] = "auto"


# ============================================================
# Jobs, Settings & Connectors
# ============================================================
class JobRunOut(BaseModel):
    id: int
    job_type: str
    trigger: str
    system_id: int | None
    status: str
    items_found: int
    new_items: int
    summary: str
    error_message: str
    started_at: datetime
    finished_at: datetime | None


class ConnectorStatusOut(BaseModel):
    id: str
    name: str
    category: str
    description: str
    enabled: bool
    requires_key: bool
    configured: bool
    env_var: str
    platforms: list[str]


class SettingsOut(BaseModel):
    gemini_api_key_masked: str
    gemini_configured: bool
    gemini_model: str
    youtube_configured: bool
    apify_configured: bool
    x_configured: bool
    meta_configured: bool
    awards_cron_day: str
    awards_cron_hour: int
    awards_cron_minute: int
    sentiment_interval_hours: int
    scheduler_enabled: bool
    webhook_configured: bool
    webhook_provider: str
    smtp_configured: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_from: str
    alert_email_to: str
    next_awards_run: str | None = None
    next_sentiment_run: str | None = None


class SettingsUpdate(BaseModel):
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    youtube_api_key: str | None = None
    apify_token: str | None = None
    x_bearer_token: str | None = None
    meta_access_token: str | None = None
    awards_cron_day: str | None = None
    awards_cron_hour: int | None = None
    awards_cron_minute: int | None = None
    sentiment_interval_hours: int | None = None
    scheduler_enabled: bool | None = None
    webhook_url: str | None = None
    webhook_provider: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    alert_email_to: str | None = None


class NotificationLogOut(BaseModel):
    id: int
    channel: str
    title: str
    status: str
    details: str
    created_at: datetime
