import { useCallback, useEffect, useState } from "react";
import {
  AlertOctagon,
  ArrowDownRight,
  ArrowUpRight,
  ExternalLink,
  Eye,
  Lightbulb,
  Loader2,
  MessageSquarePlus,
  Minus,
  Sparkles,
  Wrench,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { AppSettings, Mention, MonitoredSystem, ProblemCluster, ProblemDiagnostics } from "../types";
import { SentimentBadge } from "../components/SentimentBadge";
import { CommentImportModal } from "../components/CommentImportModal";
import { MentionDetailModal } from "../components/MentionDetailModal";
import { buildFallbackSearchUrl, normalizeExternalUrl } from "../utils/links";

interface Props {
  systems: MonitoredSystem[];
  mentions: Mention[];
  settings: AppSettings | null;
  initialSystemId?: number | null;
  onRefreshAll: () => Promise<void>;
  onToast: (msg: string) => void;
}

const SEVERITY_STYLE: Record<ProblemCluster["severity"], { badge: string; bar: string; label: string }> = {
  critica: { badge: "bg-rose-600 text-white", bar: "#e11d48", label: "Crítica" },
  alta: { badge: "bg-orange-500 text-white", bar: "#f97316", label: "Alta" },
  media: { badge: "bg-amber-100 text-amber-900 border border-amber-300", bar: "#f59e0b", label: "Média" },
  baixa: { badge: "bg-slate-200 text-slate-700", bar: "#64748b", label: "Baixa" },
};

const ACTION_LABELS: Record<ProblemCluster["action_type"], string> = {
  tecnica: "Ação Técnica / Engenharia",
  ux: "Melhoria de UX / Interface",
  comunicacao: "Comunicação / Tutorial",
  suporte: "Atendimento / Suporte",
};

export function ProblemDiagnosticsPage({
  systems,
  mentions,
  settings,
  initialSystemId,
  onRefreshAll,
  onToast,
}: Props) {
  const [selectedSystemId, setSelectedSystemId] = useState<string>(
    initialSystemId ? String(initialSystemId) : systems[0] ? String(systems[0].id) : ""
  );
  const [days, setDays] = useState<string>("365");
  const [channelGroup, setChannelGroup] = useState<string>("all");
  const [data, setData] = useState<ProblemDiagnostics | null>(null);
  const [loading, setLoading] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [selectedMention, setSelectedMention] = useState<Mention | null>(null);

  useEffect(() => {
    setSelectedSystemId(initialSystemId ? String(initialSystemId) : "");
  }, [initialSystemId]);

  const loadDiagnostics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getProblemDiagnostics({
        systemId: selectedSystemId ? Number(selectedSystemId) : null,
        days: days ? Number(days) : null,
        channelGroup,
        useAi: true,
      });
      setData(res);
    } finally {
      setLoading(false);
    }
  }, [selectedSystemId, days, channelGroup]);

  useEffect(() => {
    loadDiagnostics();
  }, [loadDiagnostics]);

  const chartData = (data?.problems || []).map((p) => ({
    name: p.title.length > 36 ? p.title.slice(0, 35) + "…" : p.title,
    fullTitle: p.title,
    relatos: p.mentions_count,
    severity: p.severity,
  }));

  const renderTrend = (trend: ProblemCluster["trend"]) => {
    if (trend === "subindo") {
      return (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700">
          <ArrowUpRight className="h-3 w-3" /> Crescendo
        </span>
      );
    }
    if (trend === "caindo") {
      return (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
          <ArrowDownRight className="h-3 w-3" /> Reduzindo
        </span>
      );
    }
    if (trend === "novo") {
      return (
        <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
          Novo no período
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
        <Minus className="h-3 w-3" /> Estável
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-slate-900">
            <AlertOctagon className="h-6 w-6 text-rose-600" />
            Diagnóstico de Problemas & Dores dos Usuários
          </h2>
          <p className="text-sm text-slate-500">
            Agrupa reclamações e comentários (Instagram, Facebook e Web) nos problemas reais que mais incomodam os cidadãos.
          </p>
        </div>

        <button
          onClick={() => setImportOpen(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
        >
          <MessageSquarePlus className="h-4 w-4" />
          Coletar / Importar Comentários (IG & FB)
        </button>
      </div>

      {/* Filters */}
      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-3">
        <select
          value={selectedSystemId}
          onChange={(e) => setSelectedSystemId(e.target.value)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium"
        >
          <option value="">Todos os sistemas</option>
          {systems.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <select
          value={channelGroup}
          onChange={(e) => setChannelGroup(e.target.value)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium"
        >
          <option value="all">Todos os canais (Redes Sociais + Internet)</option>
          <option value="instagram_facebook">Somente Instagram & Facebook</option>
          <option value="redes_sociais">Todas as Redes Sociais (IG, FB, X, YT, Reddit)</option>
          <option value="internet">Somente Internet, Notícias & Portais</option>
        </select>

        <select
          value={days}
          onChange={(e) => setDays(e.target.value)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium"
        >
          <option value="7">Últimos 7 dias</option>
          <option value="14">Últimos 14 dias</option>
          <option value="30">Últimos 30 dias</option>
          <option value="180">Últimos 6 meses</option>
          <option value="365">Último 1 ano</option>
          <option value="">Todo o histórico</option>
        </select>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center rounded-2xl border border-slate-200 bg-white py-16 text-sm text-slate-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-indigo-600" /> Diagnosticando dores dos usuários...
        </div>
      ) : data ? (
        <>
          {/* KPIs */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase text-slate-500">Relatos de Atrito / Queixas</div>
              <div className="mt-1.5 text-3xl font-bold text-slate-900">{data.total_friction_mentions}</div>
              <p className="mt-1 text-xs text-slate-500">
                de {data.total_mentions_analyzed} itens ({data.total_comments_analyzed} comentários)
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase text-slate-500">Problemas Agrupados</div>
              <div className="mt-1.5 text-3xl font-bold text-indigo-700">{data.problems_count}</div>
              <p className="mt-1 text-xs text-slate-500">
                Motor: <span className="font-mono">{data.analyzed_by}</span>
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase text-slate-500">Severidade Crítica / Alta</div>
              <div className="mt-1.5 text-3xl font-bold text-rose-600">{data.critical_or_high_count}</div>
              <p className="mt-1 text-xs text-slate-500">Prioridade imediata para engenharia/TI</p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase text-slate-500">Principal Canal de Queixas</div>
              <div className="mt-1.5 text-2xl font-bold uppercase text-slate-900">
                {data.top_complaint_channel}
              </div>
              <p className="mt-1 text-xs text-slate-500">Onde os usuários mais relatam atritos</p>
            </div>
          </div>

          {/* Executive Summary */}
          <div className="rounded-2xl border border-rose-200 bg-gradient-to-r from-rose-50 via-white to-amber-50 p-5 shadow-sm">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-rose-800">
              <Sparkles className="h-4 w-4 text-rose-600" />
              Resumo Analítico — {data.system_name}
            </div>
            <p className="mt-2 text-sm leading-relaxed text-slate-800">{data.executive_summary}</p>
          </div>

          {/* Ranking Chart */}
          {chartData.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold text-slate-900">
                Ranking dos Problemas que Mais Incomodam os Usuários
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Volume de reclamações e dúvidas agrupadas por causa raiz (cores por severidade)
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <YAxis dataKey="name" type="category" width={220} tick={{ fontSize: 11 }} stroke="#334155" />
                    <Tooltip />
                    <Bar dataKey="relatos" name="Relatos" radius={[0, 6, 6, 0]}>
                      {chartData.map((entry, idx) => (
                        <Cell key={idx} fill={SEVERITY_STYLE[entry.severity].bar} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Problem Cards */}
          <div className="space-y-4">
            {data.problems.map((prob, index) => {
              const sev = SEVERITY_STYLE[prob.severity];
              return (
                <div key={prob.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-md bg-slate-900 px-2 py-0.5 text-xs font-bold text-white">
                          #{index + 1}
                        </span>
                        <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase ${sev.badge}`}>
                          Severidade {sev.label}
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700">
                          <Wrench className="h-3 w-3" /> {ACTION_LABELS[prob.action_type]}
                        </span>
                        {renderTrend(prob.trend)}
                      </div>
                      <h3 className="text-lg font-bold text-slate-900">{prob.title}</h3>
                      <p className="text-xs text-slate-500">
                        Categoria: <strong>{prob.category}</strong> • Canais:{" "}
                        {prob.platforms.map((p) => `${p.platform.toUpperCase()} (${p.count})`).join(", ")}
                      </p>
                    </div>

                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-900">{prob.mentions_count}</div>
                      <div className="text-xs font-semibold text-slate-500">{prob.share_pct}% das queixas</div>
                    </div>
                  </div>

                  <p className="mt-3 text-sm text-slate-700">{prob.description}</p>

                  <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50/60 p-3.5 text-xs text-emerald-950">
                    <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <div>
                      <strong className="block text-emerald-900">Ação recomendada para a equipe:</strong>
                      <span>{prob.recommended_action}</span>
                    </div>
                  </div>

                  {/* Real Evidences */}
                  <div className="mt-4 space-y-2 border-t border-slate-100 pt-3">
                    <div className="text-xs font-bold uppercase tracking-wide text-slate-500">
                      Comentários e relatos reais ({prob.evidences.length})
                    </div>
                    {prob.evidences.map((ev) => {
                      const directUrl = normalizeExternalUrl(ev.url);
                      const targetUrl = directUrl || buildFallbackSearchUrl(`${ev.system_name} ${ev.excerpt.slice(0, 80)}`);
                      return (
                        <div
                          key={ev.id}
                          className="flex flex-col gap-2 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3 text-xs sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                                {ev.platform}
                              </span>
                              {ev.content_type === "comment" && (
                                <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-800">
                                  COMENTÁRIO
                                </span>
                              )}
                              <span className="font-semibold text-slate-800">{ev.author}</span>
                              {ev.date && (
                                <span className="text-slate-400">
                                  {new Date(ev.date).toLocaleDateString("pt-BR")}
                                </span>
                              )}
                            </div>
                            <p className="mt-1 text-slate-700">"{ev.excerpt}"</p>
                          </div>

                          <div className="flex shrink-0 items-center gap-2">
                            <SentimentBadge sentiment={ev.sentiment} score={ev.sentiment_score} />
                            <button
                              type="button"
                              onClick={() => {
                                const full = mentions.find((m) => m.id === ev.id);
                                if (full) setSelectedMention(full);
                              }}
                              className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 font-semibold text-white hover:bg-indigo-700"
                            >
                              <Eye className="h-3 w-3" /> Ler completo
                            </button>
                            <a
                              href={targetUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded-lg bg-white px-2.5 py-1 font-semibold text-indigo-700 border border-indigo-200 hover:bg-indigo-50"
                            >
                              {directUrl ? "Origem" : "Buscar"} <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            {data.problems.length === 0 && (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
                <p className="text-sm font-medium text-slate-700">
                  Nenhum problema ou reclamação encontrado neste filtro ainda.
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Clique em <strong>"Coletar / Importar Comentários (IG & FB)"</strong> acima para extrair comentários
                  de um post do Instagram/Facebook ou colar comentários reais e gerar o diagnóstico na hora.
                </p>
              </div>
            )}
          </div>
        </>
      ) : null}

      {importOpen && (
        <CommentImportModal
          systems={systems}
          defaultSystemId={selectedSystemId ? Number(selectedSystemId) : null}
          apifyConfigured={Boolean(settings?.apify_configured)}
          onClose={() => setImportOpen(false)}
          onCompleted={async (msg) => {
            await onRefreshAll();
            await loadDiagnostics();
            onToast(msg);
          }}
        />
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
