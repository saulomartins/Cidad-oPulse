from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitoredSystem(Base):
    """Sistema ou iniciativa em desenvolvimento/produção para atendimento ao cidadão."""

    __tablename__ = "monitored_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # JSON-encoded lists stored as text for SQLite simplicity
    urls_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    social_profiles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Perfil para Radar Mundial de Prêmios e Concursos
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="iniciativa")
    # iniciativa | producao
    uses_ai: Mapped[str] = mapped_column(String(40), nullable=False, default="sem_ia")
    # com_ia | sem_ia | hibrido
    ai_details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    citizen_area: Mapped[str] = mapped_column(String(120), nullable=False, default="Serviços Públicos Digitais")
    target_audience: Mapped[str] = mapped_column(String(250), nullable=False, default="Cidadãos em geral")
    organization_type: Mapped[str] = mapped_column(String(100), nullable=False, default="Governo Municipal")
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="Brasil")
    state_uf: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    municipality: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    impact_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    monitor_sentiment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    monitor_awards: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    mentions: Mapped[list["Mention"]] = relationship(
        "Mention", back_populates="system", cascade="all, delete-orphan"
    )
    awards: Mapped[list["AwardOpportunity"]] = relationship(
        "AwardOpportunity", back_populates="system", cascade="all, delete-orphan"
    )


class Mention(Base):
    """Menção coletada na web ou redes sociais com análise de sentimento."""

    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint("system_id", "content_hash", name="uq_system_mention_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    system_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitored_systems.id", ondelete="CASCADE"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    source_connector: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # google_news | reddit | youtube | gemini_web | apify_social | x_api | meta_api | seed
    platform: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # web | news | reddit | youtube | x | instagram | facebook | linkedin | reclame_aqui | forum
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="mention")
    # mention | post | comment
    parent_post_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    author: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    matched_keyword: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Análise de Sentimento
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default="neutro", index=True)
    # positivo | neutro | negativo
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # -1.0 .. +1.0
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    topics_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sentiment_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_crisis_signal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    analyzed_by: Mapped[str] = mapped_column(String(40), nullable=False, default="lexicon")

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    system: Mapped["MonitoredSystem"] = relationship("MonitoredSystem", back_populates="mentions")


class AwardOpportunity(Base):
    """Prêmio, concurso ou desafio mundial de software para atendimento ao cidadão."""

    __tablename__ = "award_opportunities"
    __table_args__ = (
        UniqueConstraint("system_id", "fingerprint", name="uq_system_award_fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    system_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitored_systems.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    organizer: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    official_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")

    scope: Mapped[str] = mapped_column(String(40), nullable=False, default="internacional")
    # nacional | regional | internacional
    country_region: Mapped[str] = mapped_column(String(120), nullable=False, default="Global")
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_requirement: Mapped[str] = mapped_column(String(30), nullable=False, default="ambos")
    # com_ia | sem_ia | ambos
    stage_eligibility: Mapped[str] = mapped_column(String(30), nullable=False, default="ambos")
    # iniciativa | producao | ambos

    deadline: Mapped[str] = mapped_column(String(120), nullable=False, default="Verificar edital")
    deadline_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    # ISO YYYY-MM-DD when known; empty for rolling/continuous calls
    award_status: Mapped[str] = mapped_column(String(30), nullable=False, default="previsto")
    # aberto | previsto | recorrente | encerrado
    deadline_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_source_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # aberto | previsto | recorrente | encerrado
    prize_benefits: Mapped[str] = mapped_column(Text, nullable=False, default="")
    categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Match com o sistema cadastrado
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=70)  # 0..100
    match_reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_steps: Mapped[str] = mapped_column(Text, nullable=False, default="")
    discovery_source: Mapped[str] = mapped_column(String(60), nullable=False, default="curated_catalog")
    # gemini_global_search | curated_catalog | manual

    # Pipeline interno do usuário
    pipeline_status: Mapped[str] = mapped_column(String(30), nullable=False, default="novo")
    # novo | analisando | inscrito | premiado | descartado
    user_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    system: Mapped["MonitoredSystem"] = relationship("MonitoredSystem", back_populates="awards")


class JobRun(Base):
    """Histórico de execuções automáticas (semanal/recorrente) e manuais."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # sentiment_scan | awards_radar
    trigger: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    # manual | scheduled
    system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    # running | completed | failed
    items_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSetting(Base):
    """Configurações persistidas pelo usuário via painel."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NotificationLog(Base):
    """Registro de alertas enviados por E-mail ou Webhook."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)  # email | slack | teams | generic
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # sent | failed | skipped
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AccessToken(Base):
    """Tokens de acesso criados pelo Admin para compartilhar o painel com outros usuários."""

    __tablename__ = "access_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    # viewer (somente leitura) | editor (consulta + varreduras + sistemas, sem acesso a chaves/tokens)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
