import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  Award,
  Calendar,
  ExternalLink,
  Layers,
  Loader2,
  MapPin,
  Radar,
  RefreshCw,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  AwardOpportunity,
  Mention,
  MonitoredSystem,
  ProjectStarRating,
  SentimentOverview,
} from "../types";
import { SentimentBadge } from "../components/SentimentBadge";
import { MatchScoreBadge } from "../components/MatchScoreBadge";
import { AwardsWorldMap } from "../components/AwardsWorldMap";
import { MentionDetailModal } from "../components/MentionDetailModal";
import { StarRatingCard } from "../components/StarRatingCard";
import type { NavTab } from "../components/Layout";
import { buildFallbackSearchUrl, getDisplayHost, normalizeExternalUrl } from "../utils/links";

interface Props {
  systems: MonitoredSystem[];
  selectedProject: MonitoredSystem | null;
  overview: SentimentOverview | null;
  mentions: Mention[];
  awards: AwardOpportunity[];
  starRatings: ProjectStarRating[];
  refreshingStarSystemId: number | null;
  onRefreshStarRating: (systemId: number) => Promise<void>;
  onSelectProject: (systemId: number) => void;
  onRunSentimentAll: () => Promise<void>;
  onRunAwardsAll: () => Promise<void>;
  onNavigate: (tab: NavTab) => void;
}

export function DashboardPage({
  systems,
  selectedProject,
  overview,
  mentions,
  awards,
  starRatings,
  refreshingStarSystemId,
  onRefreshStarRating,
  onSelectProject,
  onRunSentimentAll,
  onRunAwardsAll,
  onNavigate,
}: Props) {
  const [runningSentiment, setRunningSentiment] = useState(false);
  const [runningAwards, setRunningAwards] = useState(false);
  const [selectedMention, setSelectedMention] = useState<Mention | null>(null);

  const openEligibleAwards = awards.filter(
    (a) =>
      a.is_open_for_application &&
      a.award_status !== "encerrado" &&
      (a.days_remaining === null || a.days_remaining >= 15)
  );
  const highMatchAwards = openEligibleAwards.filter((a) => a.match_score >= 78);
  const crisisMentions = mentions.filter((m) => m.is_crisis_signal);

  const handleSentiment = async () => {
    setRunningSentiment(true);
    try {
      await onRunSentimentAll();
    } finally {
      setRunningSentiment(false);
    }
  };

  const handleAwards = async () => {
    setRunningAwards(true);
    try {
      await onRunAwardsAll();
    } finally {
      setRunningAwards(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            {selectedProject ? `Visão do Projeto — ${selectedProject.name}` : "Central de Monitoramento & Premiações"}
          </h2>
          <p className="text-sm text-slate-500">
            {selectedProject
              ? `${selectedProject.citizen_area} • ${selectedProject.organization_type}${
                  selectedProject.state_uf ? ` • ${selectedProject.municipality ? `${selectedProject.municipality}/` : ""}${selectedProject.state_uf}` : ""
                } — sentimento, alertas e premiações abertas deste projeto.`
              : "Sentimento dos cidadãos na internet/redes sociais e radar semanal mundial de prêmios GovTech/CivicTech."}
          </p>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <button
            onClick={handleSentiment}
            disabled={runningSentiment}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
          >
            {runningSentiment ? (
              <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
            ) : (
              <RefreshCw className="h-4 w-4 text-indigo-600" />
            )}
            {selectedProject ? "Varrer Sentimento do Projeto" : "Varrer Sentimento"}
          </button>

          <button
            onClick={handleAwards}
            disabled={runningAwards}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            {runningAwards ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Radar className="h-4 w-4" />
            )}
            {selectedProject ? "Buscar Prêmios do Projeto" : "Rodar Radar Mundial de Prêmios"}
          </button>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            {selectedProject ? "Menções do Projeto" : "Sistemas Monitorados"}
            <Layers className="h-4 w-4 text-indigo-500" />
          </div>
          <div className="mt-2 text-3xl font-bold text-slate-900">
            {selectedProject ? overview?.total_mentions ?? 0 : systems.length}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {selectedProject
              ? `${selectedProject.stage === "producao" ? "Em Produção" : "Iniciativa"} • ${
                  selectedProject.uses_ai === "sem_ia" ? "Sem IA" : "Com IA"
                }`
              : `${systems.filter((s) => s.uses_ai !== "sem_ia").length} com IA • ${
                  systems.filter((s) => s.uses_ai === "sem_ia").length
                } sem IA`}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            Índice de Sentimento
            <Activity className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-slate-900">
              {overview?.sentiment_index ?? 50}
            </span>
            <span className="text-xs font-medium text-slate-400">/ 100</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {overview?.positive_count ?? 0} pos • {overview?.neutral_count ?? 0} neu •{" "}
            {overview?.negative_count ?? 0} neg
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            Sinais de Crise
            <AlertTriangle className="h-4 w-4 text-rose-500" />
          </div>
          <div className="mt-2 text-3xl font-bold text-rose-600">{overview?.crisis_count ?? 0}</div>
          <p className="mt-1 text-xs text-slate-500">
            {crisisMentions.length > 0
              ? "Requer atenção imediata da equipe"
              : "Nenhum alerta crítico ativo"}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            Premiações Abertas (≥ 15d)
            <Award className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-2 text-3xl font-bold text-slate-900">{openEligibleAwards.length}</div>
          <p className="mt-1 text-xs text-emerald-600 font-medium">
            {highMatchAwards.length} com alta aderência (≥ 78%)
          </p>
        </div>
      </div>

      {/* App-Store / Google Play Style 5-Star Reputation Ratings per Project */}
      {starRatings.length > 0 && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {selectedProject
                  ? `Avaliação por Estrelas — ${selectedProject.name}`
                  : "Avaliação por Estrelas dos Projetos (Notícias & Comentários)"}
              </h3>
              <p className="text-xs text-slate-500">
                Nota de 1 a 5 estrelas calculada pela IA a partir da leitura das notícias e comentários reais, com justificativa detalhada.
              </p>
            </div>
          </div>

          <div className={starRatings.length === 1 ? "grid gap-4" : "grid gap-5 lg:grid-cols-2"}>
            {starRatings.map((rating) => (
              <StarRatingCard
                key={rating.system_id}
                rating={rating}
                refreshing={refreshingStarSystemId === rating.system_id}
                onRefresh={onRefreshStarRating}
                onSelectProject={!selectedProject ? onSelectProject : undefined}
              />
            ))}
          </div>
        </section>
      )}

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Evolução do Sentimento na Web & Redes</h3>
              <p className="text-xs text-slate-500">Volume diário de menções por polaridade</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => onNavigate("temporal")}
                className="rounded-lg bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
              >
                Análise Temporal (7d–1a) →
              </button>
              <button
                onClick={() => onNavigate("sentiment")}
                className="text-xs font-semibold text-indigo-600 hover:underline"
              >
                Ver todas →
              </button>
            </div>
          </div>

          <div className="h-64">
            {overview && overview.trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={overview.trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <Tooltip />
                  <Area type="monotone" dataKey="positivo" stackId="1" stroke="#10b981" fill="#a7f3d0" name="Positivo" />
                  <Area type="monotone" dataKey="neutro" stackId="1" stroke="#64748b" fill="#cbd5e1" name="Neutro" />
                  <Area type="monotone" dataKey="negativo" stackId="1" stroke="#f43f5e" fill="#fecdd3" name="Negativo" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                Execute uma varredura de sentimento para popular o gráfico temporal.
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900">Menções por Canal / Rede</h3>
          <p className="mb-4 text-xs text-slate-500">Onde os cidadãos mais falam dos seus sistemas</p>
          <div className="h-64">
            {overview && overview.by_platform.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={overview.by_platform} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <YAxis dataKey="platform" type="category" width={85} tick={{ fontSize: 11 }} stroke="#475569" />
                  <Tooltip />
                  <Bar dataKey="count" fill="#4f46e5" radius={[0, 6, 6, 0]} name="Menções" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                Sem dados de canais ainda.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Panels */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent mentions & crises */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900">Últimas Menções e Alertas</h3>
            <button
              onClick={() => onNavigate("sentiment")}
              className="text-xs font-semibold text-indigo-600 hover:underline"
            >
              Abrir feed completo →
            </button>
          </div>
          <div className="space-y-3">
            {mentions.slice(0, 5).map((m) => {
              const directUrl = normalizeExternalUrl(m.url);
              const targetUrl = directUrl || buildFallbackSearchUrl(`${m.system_name} ${m.title}`);
              const host = getDisplayHost(m.url);
              const isDemo = m.source_connector === "seed";
              return (
                <div
                  key={m.id}
                  className={`rounded-xl border p-3.5 ${
                    m.is_crisis_signal ? "border-rose-200 bg-rose-50/40" : "border-slate-200 bg-slate-50/40"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-md bg-slate-200/80 px-2 py-0.5 font-semibold uppercase text-slate-700">
                        {m.platform}
                      </span>
                      <span className="font-semibold text-slate-800">{m.system_name}</span>
                      {isDemo && (
                        <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                          Exemplo
                        </span>
                      )}
                      {m.is_crisis_signal && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-rose-600 px-2 py-0.5 text-[10px] font-bold text-white">
                          <AlertTriangle className="h-3 w-3" /> CRISE
                        </span>
                      )}
                    </div>
                    <SentimentBadge sentiment={m.sentiment} score={m.sentiment_score} />
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedMention(m)}
                    className="mt-2 block text-left text-sm font-semibold text-slate-900 hover:text-indigo-700 hover:underline"
                  >
                    {m.content_type === "comment" ? `“${m.content || m.title}”` : m.summary || m.title}
                  </button>
                  <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                    <span>
                      {m.author || m.source_connector}
                      {host && <span className="ml-1.5 font-mono text-[11px] text-slate-400">({host})</span>}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setSelectedMention(m)}
                        className="rounded-lg bg-indigo-600 px-2.5 py-1 font-semibold text-white hover:bg-indigo-700"
                      >
                        Ler texto
                      </button>
                      <a
                        href={targetUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2.5 py-1 font-semibold text-indigo-700 hover:bg-indigo-100"
                      >
                        Origem <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                </div>
              );
            })}
            {mentions.length === 0 && (
              <p className="py-8 text-center text-sm text-slate-400">Nenhuma menção registrada ainda.</p>
            )}
          </div>
        </div>

        {/* Top recommended awards (ONLY open with >= 15 days left) */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Top Premiações Mundiais Recomendadas
              </h3>
              <p className="text-[11px] text-slate-500">
                Exibindo apenas editais abertos com prazo ≥ 15 dias para inscrição
              </p>
            </div>
            <button
              onClick={() => onNavigate("awards")}
              className="text-xs font-semibold text-indigo-600 hover:underline"
            >
              Ver todas ({openEligibleAwards.length}) →
            </button>
          </div>
          <div className="space-y-3">
            {openEligibleAwards.slice(0, 6).map((a) => {
              const directUrl = normalizeExternalUrl(a.official_url);
              const targetUrl = directUrl || buildFallbackSearchUrl(`${a.title} ${a.organizer}`);
              return (
                <div key={a.id} className="rounded-xl border border-slate-200 bg-slate-50/40 p-3.5">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <a
                        href={targetUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-bold text-slate-900 hover:text-indigo-700 hover:underline"
                      >
                        {a.title}
                      </a>
                      <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                        <span>{a.organizer}</span>
                        <span>•</span>
                        <span className="inline-flex items-center gap-1 font-medium text-emerald-700">
                          <MapPin className="h-3 w-3" />
                          {a.city ? `${a.city}, ${a.country}` : a.country_region}
                        </span>
                      </p>
                    </div>
                    <MatchScoreBadge score={a.match_score} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                    <span className="rounded-md bg-indigo-50 px-2 py-0.5 font-semibold text-indigo-700">
                      Para: {a.system_name}
                    </span>
                    <span className="rounded-md bg-slate-200/70 px-2 py-0.5 text-slate-700">
                      IA: {a.ai_requirement === "ambos" ? "Com ou sem IA" : a.ai_requirement === "com_ia" ? "Exige IA" : "Sem IA"}
                    </span>
                    <span className="rounded-md bg-slate-200/70 px-2 py-0.5 text-slate-700">
                      Estágio: {a.stage_eligibility === "ambos" ? "Iniciativa ou Produção" : a.stage_eligibility}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600 line-clamp-2">{a.match_reasoning}</p>
                  <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
                      <Calendar className="h-3.5 w-3.5" />
                      {a.days_remaining !== null
                        ? `Faltam ${a.days_remaining} dias (${a.deadline_date})`
                        : a.deadline}
                    </span>
                    <a
                      href={targetUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-2.5 py-1 font-semibold text-white hover:bg-slate-800"
                    >
                      Acessar edital <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                </div>
              );
            })}
            {openEligibleAwards.length === 0 && (
              <p className="py-8 text-center text-sm text-slate-400">
                Nenhuma premiação com prazo ≥ 15 dias disponível. Rode o Radar Mundial de Prêmios.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Interactive World Map on Dashboard */}
      {openEligibleAwards.length > 0 && (
        <AwardsWorldMap awards={openEligibleAwards} heightClass="h-[420px]" />
      )}

      {selectedMention && (
        <MentionDetailModal
          mention={selectedMention}
          parentPost={
            selectedMention.content_type === "comment" && selectedMention.parent_post_url
              ? mentions.find(
                  (p) =>
                    p.id !== selectedMention.id &&
                    p.content_type !== "comment" &&
                    (p.url === selectedMention.parent_post_url ||
                      p.parent_post_url === selectedMention.parent_post_url)
                ) || null
              : null
          }
          onClose={() => setSelectedMention(null)}
        />
      )}
    </div>
  );
}
