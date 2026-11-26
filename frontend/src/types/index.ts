export type SystemStage = "iniciativa" | "producao";
export type AiUsage = "com_ia" | "sem_ia" | "hibrido";
export type SentimentType = "positivo" | "neutro" | "negativo";
export type PipelineStatus = "novo" | "analisando" | "inscrito" | "premiado" | "descartado";

export interface MonitoredSystem {
  id: number;
  slug: string;
  name: string;
  description: string;
  urls: string[];
  keywords: string[];
  social_profiles: string[];
  stage: SystemStage;
  uses_ai: AiUsage;
  ai_details: string;
  citizen_area: string;
  target_audience: string;
  organization_type: string;
  country: string;
  state_uf: string;
  municipality: string;
  impact_summary: string;
  monitor_sentiment: boolean;
  monitor_awards: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  mentions_count: number;
  avg_sentiment: number;
  awards_count: number;
}

export interface SystemPayload {
  name: string;
  description: string;
  urls: string[];
  keywords: string[];
  social_profiles: string[];
  stage: SystemStage;
  uses_ai: AiUsage;
  ai_details: string;
  citizen_area: string;
  target_audience: string;
  organization_type: string;
  country: string;
  state_uf: string;
  municipality: string;
  impact_summary: string;
  monitor_sentiment: boolean;
  monitor_awards: boolean;
  is_active: boolean;
}

export interface Mention {
  id: number;
  system_id: number;
  system_name: string;
  source_connector: string;
  platform: string;
  content_type?: string;
  parent_post_url?: string;
  title: string;
  content: string;
  url: string;
  author: string;
  matched_keyword: string;
  published_at: string | null;
  sentiment: SentimentType;
  sentiment_score: number;
  confidence: number;
  topics: string[];
  summary: string;
  sentiment_reason?: string;
  evidence_quote?: string;
  is_crisis_signal: boolean;
  analyzed_by: string;
  collected_at: string;
}

export interface SentimentTrendPoint {
  date: string;
  positivo: number;
  neutro: number;
  negativo: number;
  avg_score: number;
}

export interface SentimentOverview {
  total_mentions: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  crisis_count: number;
  avg_score: number;
  sentiment_index: number;
  by_platform: { platform: string; count: number }[];
  top_topics: { topic: string; count: number }[];
  trend: SentimentTrendPoint[];
}

export interface TemporalWindowSummary {
  days: number;
  label: string;
  total_mentions: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  crisis_count: number;
  avg_score: number;
  sentiment_index: number;
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
}

export interface TemporalSeriesPoint {
  bucket: string;
  label: string;
  positivo: number;
  neutro: number;
  negativo: number;
  total: number;
  avg_score: number;
  sentiment_index: number | null;
}

export interface ChannelGroupSummary {
  group: "redes_sociais" | "internet" | string;
  label: string;
  total_mentions: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  sentiment_index: number;
  platforms: { platform: string; count: number }[];
}

export interface TemporalAnalysis {
  system_id: number | null;
  system_name: string;
  period_days: number;
  period_label: string;
  granularity: "day" | "month";
  date_from: string;
  date_to: string;
  current: TemporalWindowSummary;
  previous: TemporalWindowSummary;
  mentions_delta: number;
  sentiment_index_delta: number;
  trend_direction: "melhorando" | "piorando" | "estavel" | "sem_dados";
  narrative_summary: string;
  windows_summary: TemporalWindowSummary[];
  series: TemporalSeriesPoint[];
  channel_groups: ChannelGroupSummary[];
  top_topics: { topic: string; count: number }[];
}

export interface ProblemEvidence {
  id: number;
  system_name: string;
  platform: string;
  content_type: string;
  author: string;
  title: string;
  excerpt: string;
  url: string;
  sentiment: SentimentType;
  sentiment_score: number;
  is_crisis_signal: boolean;
  date: string;
}

export interface ProblemCluster {
  id: string;
  title: string;
  category: string;
  severity: "critica" | "alta" | "media" | "baixa";
  action_type: "tecnica" | "ux" | "comunicacao" | "suporte";
  mentions_count: number;
  share_pct: number;
  avg_sentiment: number;
  trend: "subindo" | "caindo" | "estavel" | "novo";
  platforms: { platform: string; count: number }[];
  description: string;
  recommended_action: string;
  evidences: ProblemEvidence[];
}

export interface ProblemDiagnostics {
  system_id: number | null;
  system_name: string;
  days: number | null;
  channel_group: string;
  total_mentions_analyzed: number;
  total_comments_analyzed: number;
  total_friction_mentions: number;
  problems_count: number;
  critical_or_high_count: number;
  top_complaint_channel: string;
  analyzed_by: string;
  executive_summary: string;
  problems: ProblemCluster[];
}

export interface AwardOpportunity {
  id: number;
  system_id: number;
  system_name: string;
  title: string;
  organizer: string;
  description: string;
  official_url: string;
  scope: "nacional" | "regional" | "internacional" | string;
  country_region: string;
  country: string;
  city: string;
  latitude: number | null;
  longitude: number | null;
  ai_requirement: "com_ia" | "sem_ia" | "ambos" | string;
  stage_eligibility: "iniciativa" | "producao" | "ambos" | string;
  deadline: string;
  deadline_date: string;
  days_remaining: number | null;
  is_open_for_application: boolean;
  award_status: string;
  deadline_verified_at?: string | null;
  deadline_source_note?: string;
  prize_benefits: string;
  categories: string[];
  match_score: number;
  match_reasoning: string;
  next_steps: string;
  discovery_source: string;
  pipeline_status: PipelineStatus;
  user_notes: string;
  discovered_at: string;
  updated_at: string;
}

export interface JobRun {
  id: number;
  job_type: "sentiment_scan" | "awards_radar" | string;
  trigger: "manual" | "scheduled" | string;
  system_id: number | null;
  status: "running" | "completed" | "failed" | string;
  items_found: number;
  new_items: number;
  summary: string;
  error_message: string;
  started_at: string;
  finished_at: string | null;
}

export interface ConnectorStatus {
  id: string;
  name: string;
  category: string;
  description: string;
  enabled: boolean;
  requires_key: boolean;
  configured: boolean;
  env_var: string;
  platforms: string[];
}

export interface AppSettings {
  gemini_api_key_masked: string;
  gemini_configured: boolean;
  gemini_model: string;
  youtube_configured: boolean;
  apify_configured: boolean;
  x_configured: boolean;
  meta_configured: boolean;
  awards_cron_day: string;
  awards_cron_hour: number;
  awards_cron_minute: number;
  sentiment_interval_hours: number;
  scheduler_enabled: boolean;
  webhook_configured: boolean;
  webhook_provider: string;
  smtp_configured: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_from: string;
  alert_email_to: string;
  next_awards_run: string | null;
  next_sentiment_run: string | null;
}

export interface NotificationLog {
  id: number;
  channel: string;
  title: string;
  status: string;
  details: string;
  created_at: string;
}
