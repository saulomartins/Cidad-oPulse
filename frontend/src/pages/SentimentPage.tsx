import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
  Eye,
  Filter,
  Link2,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import type { Mention, MonitoredSystem, SentimentOverview } from "../types";
import { SentimentBadge } from "../components/SentimentBadge";
import { MentionDetailModal } from "../components/MentionDetailModal";
import { buildFallbackSearchUrl, getDisplayHost, normalizeExternalUrl } from "../utils/links";

interface Props {
  systems: MonitoredSystem[];
  mentions: Mention[];
  overview: SentimentOverview | null;
  initialSystemId?: number | null;
  isAdmin?: boolean;
  onScan: (systemId?: number) => Promise<void>;
  onCleanupIrrelevant: (systemId?: number) => Promise<void>;
  onDeleteMention: (id: number) => Promise<void>;
}

export function SentimentPage({
  systems,
  mentions,
  overview,
  initialSystemId,
  isAdmin = false,
  onScan,
  onCleanupIrrelevant,
  onDeleteMention,
}: Props) {
  const [selectedSystem, setSelectedSystem] = useState<string>(initialSystemId ? String(initialSystemId) : "");
  const [selectedSentiment, setSelectedSentiment] = useState<string>("");
  const [selectedPlatform, setSelectedPlatform] = useState<string>("");
  const [crisisOnly, setCrisisOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [scanning, setScanning] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [selectedMention, setSelectedMention] = useState<Mention | null>(null);

  useEffect(() => {
    setSelectedSystem(initialSystemId ? String(initialSystemId) : "");
  }, [initialSystemId]);

  const handleCopy = async (id: number, url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // ignore clipboard errors in restricted contexts
    }
  };

  const platforms = Array.from(new Set(mentions.map((m) => m.platform))).sort();

  const filtered = mentions.filter((m) => {
    if (selectedSystem && String(m.system_id) !== selectedSystem) return false;
    if (selectedSentiment && m.sentiment !== selectedSentiment) return false;
    if (selectedPlatform && m.platform !== selectedPlatform) return false;
    if (crisisOnly && !m.is_crisis_signal) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      const hay = `${m.title} ${m.content} ${m.summary} ${m.author} ${m.topics.join(" ")}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const handleScan = async () => {
    setScanning(true);
    try {
      await onScan(selectedSystem ? Number(selectedSystem) : undefined);
    } finally {
      setScanning(false);
    }
  };

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      await onCleanupIrrelevant(selectedSystem ? Number(selectedSystem) : undefined);
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Monitor de Sentimento — Internet & Redes Sociais
          </h2>
          <p className="text-sm text-slate-500">
            Acompanhe o que cidadãos, imprensa e redes sociais estão falando sobre seus sistemas em tempo real.
          </p>
        </div>

        {isAdmin && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleCleanup}
              disabled={cleaning}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
              title="Reavalia menções salvas e remove falsos positivos fora do contexto do sistema"
            >
              {cleaning ? <Loader2 className="h-4 w-4 animate-spin text-indigo-600" /> : <Sparkles className="h-4 w-4 text-indigo-600" />}
              Limpar irrelevantes
            </button>

            <button
              onClick={handleScan}
              disabled={scanning}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              {selectedSystem ? "Varrer Sistema Selecionado" : "Varrer Todos os Sistemas"}
            </button>
          </div>
        )}
      </div>

      {/* Top Topics Strip */}
      {overview && overview.top_topics.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Principais temas:
          </span>
          {overview.top_topics.map((t) => (
            <button
              key={t.topic}
              onClick={() => setSearch(search === t.topic ? "" : t.topic)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                search === t.topic
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              #{t.topic} <span className="opacity-70">({t.count})</span>
            </button>
          ))}
        </div>
      )}

      {/* Filter Bar */}
      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-5">
        <div className="relative md:col-span-2">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar texto, autor, tema..."
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <select
          value={selectedSystem}
          onChange={(e) => setSelectedSystem(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Todos os sistemas</option>
          {systems.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <select
          value={selectedSentiment}
          onChange={(e) => setSelectedSentiment(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Todos os sentimentos</option>
          <option value="positivo">Positivo</option>
          <option value="neutro">Neutro</option>
          <option value="negativo">Negativo</option>
        </select>

        <select
          value={selectedPlatform}
          onChange={(e) => setSelectedPlatform(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Todos os canais</option>
          {platforms.map((p) => (
            <option key={p} value={p}>
              {p.toUpperCase()}
            </option>
          ))}
        </select>

        <div className="flex items-center justify-between md:col-span-5">
          <label className="inline-flex items-center gap-2 text-xs font-semibold text-rose-700">
            <input
              type="checkbox"
              checked={crisisOnly}
              onChange={(e) => setCrisisOnly(e.target.checked)}
              className="h-4 w-4 rounded border-rose-300 text-rose-600"
            />
            Mostrar apenas sinais de crise / indisponibilidade grave
          </label>

          <span className="inline-flex items-center gap-1 text-xs text-slate-500">
            <Filter className="h-3.5 w-3.5" /> {filtered.length} de {mentions.length} menções
          </span>
        </div>
      </div>

      {/* Feed */}
      <div className="space-y-3">
        {filtered.map((m) => {
          const directUrl = normalizeExternalUrl(m.url);
          const targetUrl = directUrl || buildFallbackSearchUrl(`${m.system_name} ${m.title}`);
          const host = getDisplayHost(m.url);
          const isDemo = m.source_connector === "seed";
          return (
            <article
              key={m.id}
              className={`rounded-2xl border bg-white p-5 shadow-sm transition hover:border-indigo-200 ${
                m.is_crisis_signal ? "border-rose-300 ring-1 ring-rose-100" : "border-slate-200"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-md bg-slate-900 px-2 py-0.5 font-bold uppercase text-white">
                    {m.platform}
                  </span>
                  <span className="rounded-md bg-indigo-50 px-2.5 py-0.5 font-semibold text-indigo-700">
                    {m.system_name}
                  </span>
                  <span className="text-slate-500">via {m.source_connector}</span>
                  {isDemo && (
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                      Dado de demonstração
                    </span>
                  )}
                  {m.is_crisis_signal && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-rose-600 px-2.5 py-0.5 font-bold text-white">
                      <AlertTriangle className="h-3 w-3" /> SINAL DE CRISE
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <SentimentBadge sentiment={m.sentiment} score={m.sentiment_score} />
                  {isAdmin && (
                    <button
                      onClick={() => onDeleteMention(m.id)}
                      className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-rose-600"
                      title="Remover menção"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              <h3 className="mt-3 text-base font-bold text-slate-900">
                <button
                  type="button"
                  onClick={() => setSelectedMention(m)}
                  className="inline-flex items-start gap-1.5 text-left hover:text-indigo-700 hover:underline"
                >
                  <span>{m.content_type === "comment" ? `“${m.content || m.title}”` : m.title}</span>
                </button>
              </h3>

              {/* Explanation + Verbatim Quote */}
              <div
                className={`mt-2.5 space-y-1.5 rounded-xl border p-3 text-xs ${
                  m.sentiment === "positivo"
                    ? "border-emerald-200 bg-emerald-50/60"
                    : m.sentiment === "negativo"
                    ? "border-rose-200 bg-rose-50/60"
                    : "border-slate-200 bg-slate-100/70"
                }`}
              >
                <div className="text-slate-800">
                  <strong>
                    {m.sentiment === "positivo"
                      ? "Por que é Positivo:"
                      : m.sentiment === "negativo"
                      ? "Por que é Negativo:"
                      : "Por que é Neutro:"}
                  </strong>{" "}
                  {m.sentiment_reason || m.summary || "Classificação baseada no tom geral da publicação."}
                </div>
                {(m.evidence_quote || m.content) && (
                  <blockquote
                    className={`border-l-4 pl-2.5 italic ${
                      m.sentiment === "positivo"
                        ? "border-l-emerald-500 text-emerald-950"
                        : m.sentiment === "negativo"
                        ? "border-l-rose-500 text-rose-950"
                        : "border-l-slate-400 text-slate-700"
                    }`}
                  >
                    “{m.evidence_quote || m.content}”
                  </blockquote>
                )}
              </div>

              {m.content && m.content !== (m.evidence_quote || "") && (
                <p className="mt-2 text-sm text-slate-600">{m.content}</p>
              )}

              {/* Direct Source Link Bar */}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200/80 bg-slate-50 px-3 py-2 text-xs">
                <div className="flex min-w-0 items-center gap-2">
                  <Link2 className="h-3.5 w-3.5 shrink-0 text-indigo-600" />
                  {directUrl ? (
                    <a
                      href={directUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate font-mono text-[11px] text-indigo-700 hover:underline"
                      title={directUrl}
                    >
                      {directUrl}
                    </a>
                  ) : (
                    <span className="text-slate-500">
                      Link direto não retornado pelo conector — use a busca rápida ao lado
                    </span>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedMention(m)}
                    className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-2.5 py-1 font-semibold text-white hover:bg-slate-800"
                  >
                    <Eye className="h-3.5 w-3.5" /> Ler texto e publicação
                  </button>
                  {directUrl && (
                    <button
                      type="button"
                      onClick={() => handleCopy(m.id, directUrl)}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 font-medium text-slate-700 hover:bg-slate-100"
                    >
                      {copiedId === m.id ? (
                        <>
                          <Check className="h-3 w-3 text-emerald-600" /> Copiado
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3" /> Copiar link
                        </>
                      )}
                    </button>
                  )}
                  <a
                    href={targetUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1 font-semibold text-white hover:bg-indigo-700"
                  >
                    {directUrl ? `Abrir (${host || "origem"})` : "Buscar na web"}{" "}
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3 text-xs">
                <div className="flex flex-wrap items-center gap-1.5">
                  {m.topics.map((t) => (
                    <span key={t} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-slate-600">
                      #{t}
                    </span>
                  ))}
                  {m.matched_keyword && (
                    <span className="text-slate-400">• Termo: "{m.matched_keyword}"</span>
                  )}
                </div>

                <div className="flex items-center gap-3 text-slate-500">
                  <span>{m.author}</span>
                  <span>
                    {new Date(m.published_at || m.collected_at).toLocaleDateString("pt-BR")}
                  </span>
                </div>
              </div>
            </article>
          );
        })}

        {filtered.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-slate-500">
            Nenhuma menção encontrada com os filtros atuais.
          </div>
        )}
      </div>

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
