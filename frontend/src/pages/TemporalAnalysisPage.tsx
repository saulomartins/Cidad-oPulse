import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarRange,
  ExternalLink,
  Eye,
  Globe,
  Loader2,
  MessageSquareQuote,
  Minus,
  RefreshCw,
  Share2,
  TrendingUp,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { Mention, MonitoredSystem, TemporalAnalysis } from "../types";
import { SentimentBadge } from "../components/SentimentBadge";
import { MentionDetailModal } from "../components/MentionDetailModal";
import { buildFallbackSearchUrl, getDisplayHost, normalizeExternalUrl } from "../utils/links";

interface Props {
  systems: MonitoredSystem[];
  allMentions?: Mention[];
  initialSystemId?: number | null;
  onScanPeriod: (systemId: number | undefined, lookbackDays: number) => Promise<void>;
}

const PERIOD_OPTIONS = [
  { days: 7, label: "7 dias" },
  { days: 14, label: "14 dias" },
  { days: 30, label: "30 dias" },
  { days: 180, label: "6 meses" },
  { days: 365, label: "1 ano" },
];

export function TemporalAnalysisPage({ systems, allMentions = [], initialSystemId, onScanPeriod }: Props) {
  const [selectedSystemId, setSelectedSystemId] = useState<string>(
    initialSystemId ? String(initialSystemId) : systems[0] ? String(systems[0].id) : ""
  );
  const [days, setDays] = useState<number>(365);
  const [analysis, setAnalysis] = useState<TemporalAnalysis | null>(null);
  const [periodMentions, setPeriodMentions] = useState<Mention[]>([]);
  const [sentimentFilter, setSentimentFilter] = useState<"todos" | "positivo" | "neutro" | "negativo">("todos");
  const [selectedMention, setSelectedMention] = useState<Mention | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [scanning, setScanning] = useState<boolean>(false);

  useEffect(() => {
    setSelectedSystemId(initialSystemId ? String(initialSystemId) : "");
  }, [initialSystemId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const sysNum = selectedSystemId ? Number(selectedSystemId) : undefined;
      const [temporalRes, mentionsRes] = await Promise.all([
        api.getTemporalAnalysis(sysNum ?? null, days),
        api.listMentions({ system_id: sysNum, days, limit: 50 }),
      ]);
      setAnalysis(temporalRes);
      setPeriodMentions(mentionsRes);
    } finally {
      setLoading(false);
    }
  }, [selectedSystemId, days]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleScanPeriod = async () => {
    setScanning(true);
    try {
      await onScanPeriod(selectedSystemId ? Number(selectedSystemId) : undefined, days);
      await loadData();
    } finally {
      setScanning(false);
    }
  };

  const trendBadge = () => {
    if (!analysis) return null;
    if (analysis.trend_direction === "melhorando") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
          <ArrowUpRight className="h-3.5 w-3.5" /> Em melhora
          {analysis.sentiment_index_delta !== 0 && ` (+${analysis.sentiment_index_delta} pts)`}
        </span>
      );
    }
    if (analysis.trend_direction === "piorando") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-3 py-1 text-xs font-bold text-rose-800">
          <ArrowDownRight className="h-3.5 w-3.5" /> Em queda
          {analysis.sentiment_index_delta !== 0 && ` (${analysis.sentiment_index_delta} pts)`}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-200 px-3 py-1 text-xs font-bold text-slate-700">
        <Minus className="h-3.5 w-3.5" />
        {analysis.trend_direction === "sem_dados" ? "Sem dados no período" : "Estável"}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-slate-900">
            <TrendingUp className="h-6 w-6 text-indigo-600" />
            Análise Temporal de Sentimento
          </h2>
          <p className="text-sm text-slate-500">
            Compare como seus sistemas estão nas redes sociais e na internet em janelas de 7 dias, 14 dias, 30 dias, 6 meses e 1 ano.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={selectedSystemId}
            onChange={(e) => setSelectedSystemId(e.target.value)}
            className="rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-800 shadow-sm"
          >
            <option value="">Todos os sistemas</option>
            {systems.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>

          <button
            onClick={handleScanPeriod}
            disabled={scanning}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Coletar período ({PERIOD_OPTIONS.find((p) => p.days === days)?.label})
          </button>
        </div>
      </div>

      {/* Period Selector Pills */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <CalendarRange className="h-4 w-4 text-indigo-600" /> Janela:
          </span>
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              onClick={() => setDays(opt.days)}
              className={`rounded-xl px-4 py-1.5 text-sm font-semibold transition ${
                days === opt.days
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {analysis && (
          <span className="text-xs text-slate-500">
            Intervalo: <strong>{analysis.date_from}</strong> até <strong>{analysis.date_to}</strong>{" "}
            (visão {analysis.granularity === "month" ? "mensal" : "diária"})
          </span>
        )}
      </div>

      {/* 5-Window Simultaneous Comparison Grid */}
      {analysis && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {analysis.windows_summary.map((win) => {
            const active = win.days === days;
            return (
              <button
                key={win.days}
                type="button"
                onClick={() => setDays(win.days)}
                className={`rounded-2xl border p-4 text-left transition ${
                  active
                    ? "border-indigo-500 bg-indigo-50/60 ring-2 ring-indigo-200"
                    : "border-slate-200 bg-white hover:border-indigo-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
                    {win.label}
                  </span>
                  <span
                    className={`rounded-md px-2 py-0.5 text-xs font-bold ${
                      win.total_mentions === 0
                        ? "bg-slate-100 text-slate-500"
                        : win.sentiment_index >= 65
                        ? "bg-emerald-100 text-emerald-800"
                        : win.sentiment_index <= 40
                        ? "bg-rose-100 text-rose-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {win.total_mentions > 0 ? `${win.sentiment_index}/100` : "—"}
                  </span>
                </div>

                <div className="mt-2 flex items-baseline gap-1.5">
                  <span className="text-2xl font-bold text-slate-900">{win.total_mentions}</span>
                  <span className="text-xs text-slate-500">menções</span>
                </div>

                {/* Mini sentiment distribution bar */}
                <div className="mt-2.5 flex h-2 w-full overflow-hidden rounded-full bg-slate-200">
                  {win.total_mentions > 0 && (
                    <>
                      <div style={{ width: `${win.positive_pct}%` }} className="bg-emerald-500" />
                      <div style={{ width: `${win.neutral_pct}%` }} className="bg-slate-400" />
                      <div style={{ width: `${win.negative_pct}%` }} className="bg-rose-500" />
                    </>
                  )}
                </div>

                <div className="mt-2 flex justify-between text-[11px] text-slate-500">
                  <span className="text-emerald-700 font-medium">{win.positive_pct}% pos</span>
                  <span className="text-rose-700 font-medium">{win.negative_pct}% neg</span>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {loading && !analysis ? (
        <div className="flex items-center justify-center rounded-2xl border border-slate-200 bg-white py-16 text-sm text-slate-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-indigo-600" /> Calculando análise temporal...
        </div>
      ) : analysis ? (
        <>
          {/* Executive Narrative + Delta */}
          <div className="rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-cyan-50 p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs font-bold uppercase tracking-wide text-indigo-700">
                Diagnóstico Executivo — {analysis.system_name} ({analysis.period_label})
              </div>
              {trendBadge()}
            </div>
            <p className="mt-2 text-sm leading-relaxed text-slate-800">{analysis.narrative_summary}</p>
            <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-600">
              <span>
                Período atual: <strong>{analysis.current.total_mentions}</strong> menções (Índice{" "}
                <strong>{analysis.current.sentiment_index}/100</strong>)
              </span>
              <span>
                Período anterior ({analysis.period_label}):{" "}
                <strong>{analysis.previous.total_mentions}</strong> menções
                {analysis.previous.total_mentions > 0 && ` (Índice ${analysis.previous.sentiment_index}/100)`}
              </span>
              <span>
                Variação de volume:{" "}
                <strong className={analysis.mentions_delta >= 0 ? "text-indigo-700" : "text-slate-700"}>
                  {analysis.mentions_delta > 0 ? `+${analysis.mentions_delta}` : analysis.mentions_delta}
                </strong>
              </span>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold text-slate-900">
                Volume de Menções por Polaridade ({analysis.period_label})
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Distribuição {analysis.granularity === "month" ? "mês a mês" : "dia a dia"} de menções positivas, neutras e negativas
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analysis.series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <Tooltip />
                    <Bar dataKey="positivo" stackId="s" fill="#10b981" name="Positivo" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="neutro" stackId="s" fill="#94a3b8" name="Neutro" />
                    <Bar dataKey="negativo" stackId="s" fill="#f43f5e" name="Negativo" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold text-slate-900">
                Evolução do Índice de Sentimento (0–100)
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Acima de 50 indica percepção positiva; abaixo de 50 indica predominância de críticas
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={analysis.series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <Tooltip />
                    <ReferenceLine y={50} stroke="#cbd5e1" strokeDasharray="4 4" />
                    <Line
                      type="monotone"
                      dataKey="sentiment_index"
                      stroke="#4f46e5"
                      strokeWidth={2.5}
                      dot={{ r: 4, fill: "#4f46e5" }}
                      connectNulls
                      name="Índice (0–100)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Redes Sociais vs Internet Breakdown */}
          <div className="grid gap-4 md:grid-cols-2">
            {analysis.channel_groups.map((grp) => {
              const Icon = grp.group === "redes_sociais" ? Share2 : Globe;
              return (
                <div key={grp.group} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
                      <Icon className="h-4 w-4 text-indigo-600" />
                      {grp.label}
                    </h3>
                    <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-800">
                      Índice: {grp.total_mentions > 0 ? `${grp.sentiment_index}/100` : "—"}
                    </span>
                  </div>

                  <div className="mt-3 flex items-baseline gap-4 text-xs text-slate-600">
                    <span>
                      <strong className="text-xl text-slate-900">{grp.total_mentions}</strong> menções
                    </span>
                    <span className="text-emerald-700 font-semibold">{grp.positive_count} positivas</span>
                    <span className="text-slate-600">{grp.neutral_count} neutras</span>
                    <span className="text-rose-700 font-semibold">{grp.negative_count} negativas</span>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {grp.platforms.length > 0 ? (
                      grp.platforms.map((p) => (
                        <span
                          key={p.platform}
                          className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700"
                        >
                          {p.platform.toUpperCase()} ({p.count})
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-400">
                        Nenhuma menção neste grupo no período de {analysis.period_label}.
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Mentions inside this window with explicit WHY + VERBATIM QUOTE */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Evidências do Sentimento em {analysis.period_label} ({periodMentions.length})
                </h3>
                <p className="text-xs text-slate-500">
                  Veja exatamente por que cada menção ou comentário foi classificado como positivo, neutro ou negativo e o trecho comprobatório
                </p>
              </div>

              <div className="flex flex-wrap gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={() => setSentimentFilter("todos")}
                  className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                    sentimentFilter === "todos"
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  Todos ({periodMentions.length})
                </button>
                <button
                  type="button"
                  onClick={() => setSentimentFilter("positivo")}
                  className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                    sentimentFilter === "positivo"
                      ? "bg-emerald-600 text-white"
                      : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                  }`}
                >
                  🟢 Positivos ({periodMentions.filter((x) => x.sentiment === "positivo").length})
                </button>
                <button
                  type="button"
                  onClick={() => setSentimentFilter("neutro")}
                  className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                    sentimentFilter === "neutro"
                      ? "bg-slate-600 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  ⚪ Neutros ({periodMentions.filter((x) => x.sentiment === "neutro").length})
                </button>
                <button
                  type="button"
                  onClick={() => setSentimentFilter("negativo")}
                  className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                    sentimentFilter === "negativo"
                      ? "bg-rose-600 text-white"
                      : "bg-rose-50 text-rose-800 hover:bg-rose-100"
                  }`}
                >
                  🔴 Negativos ({periodMentions.filter((x) => x.sentiment === "negativo").length})
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {periodMentions
                .filter((m) => sentimentFilter === "todos" || m.sentiment === sentimentFilter)
                .map((m) => {
                  const directUrl = normalizeExternalUrl(m.url);
                  const targetUrl = directUrl || buildFallbackSearchUrl(`${m.system_name} ${m.title}`);
                  const host = getDisplayHost(m.url);
                  const toneBox =
                    m.sentiment === "positivo"
                      ? "border-emerald-200 bg-emerald-50/60"
                      : m.sentiment === "negativo"
                      ? "border-rose-200 bg-rose-50/60"
                      : "border-slate-200 bg-slate-100/70";
                  const quoteBorder =
                    m.sentiment === "positivo"
                      ? "border-l-emerald-500 text-emerald-950"
                      : m.sentiment === "negativo"
                      ? "border-l-rose-500 text-rose-950"
                      : "border-l-slate-400 text-slate-800";
                  const whyLabel =
                    m.sentiment === "positivo"
                      ? "Por que é Positivo:"
                      : m.sentiment === "negativo"
                      ? "Por que é Negativo:"
                      : "Por que é Neutro:";
                  const quoteText = (m.evidence_quote || m.content || m.title).trim();
                  const isComment = m.content_type === "comment";
                  const primaryHeading = isComment ? `“${m.content || m.title}”` : m.title;

                  return (
                    <div
                      key={m.id}
                      className={`rounded-xl border p-4 transition hover:border-indigo-300 ${
                        m.is_crisis_signal ? "border-rose-300 bg-rose-50/30" : "border-slate-200 bg-white"
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="rounded bg-slate-900 px-1.5 py-0.5 font-bold uppercase text-white">
                              {m.platform}
                            </span>
                            {isComment && (
                              <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-800">
                                COMENTÁRIO
                              </span>
                            )}
                            <span className="font-semibold text-indigo-700">{m.system_name}</span>
                            <span className="text-slate-500">{m.author}</span>
                            <span className="text-slate-400">
                              • {new Date(m.published_at || m.collected_at).toLocaleDateString("pt-BR")}
                            </span>
                            {m.is_crisis_signal && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-rose-600 px-2 py-0.5 text-[10px] font-bold text-white">
                                <AlertTriangle className="h-3 w-3" /> CRISE
                              </span>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => setSelectedMention(m)}
                            className="block text-left text-sm font-bold text-slate-900 hover:text-indigo-700 hover:underline"
                          >
                            {primaryHeading}
                          </button>
                        </div>

                        <div className="flex shrink-0 flex-wrap items-center gap-2">
                          <SentimentBadge sentiment={m.sentiment} score={m.sentiment_score} />
                          <button
                            type="button"
                            onClick={() => setSelectedMention(m)}
                            className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
                          >
                            <Eye className="h-3.5 w-3.5" /> Ver texto e publicação
                          </button>
                          <a
                            href={targetUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                            title={directUrl || "Abrir na origem"}
                          >
                            {directUrl ? (host || "Origem") : "Buscar"} <ExternalLink className="h-3 w-3" />
                          </a>
                        </div>
                      </div>

                      {/* WHY + VERBATIM EVIDENCE QUOTE BOX */}
                      <div className={`mt-3 space-y-2 rounded-xl border p-3 text-xs ${toneBox}`}>
                        <div className="text-slate-800">
                          <strong className="font-bold">{whyLabel}</strong>{" "}
                          <span>{m.sentiment_reason || m.summary || "Classificação baseada no tom geral do relato."}</span>
                        </div>
                        <blockquote className={`border-l-4 pl-3 italic leading-relaxed ${quoteBorder}`}>
                          <span className="mb-0.5 flex items-center gap-1 text-[10px] font-bold not-italic uppercase tracking-wide opacity-75">
                            <MessageSquareQuote className="h-3 w-3" /> Trecho identificado:
                          </span>
                          “{quoteText}”
                        </blockquote>
                      </div>
                    </div>
                  );
                })}

              {periodMentions.filter((m) => sentimentFilter === "todos" || m.sentiment === sentimentFilter).length ===
                0 && (
                <p className="py-8 text-center text-sm text-slate-400">
                  Nenhuma menção com este filtro na janela selecionada.
                </p>
              )}
            </div>
          </div>
        </>
      ) : null}

      {selectedMention && (
        <MentionDetailModal
          mention={selectedMention}
          parentPost={
            selectedMention.content_type === "comment" && selectedMention.parent_post_url
              ? [...periodMentions, ...allMentions].find(
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
