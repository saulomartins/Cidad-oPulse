import { useCallback, useEffect, useState } from "react";
import {
  Archive,
  Award,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Cpu,
  Download,
  ExternalLink,
  EyeOff,
  Globe2,
  Link2,
  List,
  Loader2,
  Map as MapIcon,
  MapPin,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { AwardOpportunity, MonitoredSystem, PipelineStatus } from "../types";
import { MatchScoreBadge } from "../components/MatchScoreBadge";
import { AwardsWorldMap } from "../components/AwardsWorldMap";
import { api } from "../api/client";
import { buildFallbackSearchUrl, normalizeExternalUrl } from "../utils/links";

interface Props {
  systems: MonitoredSystem[];
  awards: AwardOpportunity[];
  initialSystemId?: number | null;
  onRunAwardsScan: (payload: {
    system_id?: number | null;
    focus_scope: "todos" | "internacional" | "nacional";
    include_ai_filter: "auto" | "com_ia" | "sem_ia" | "ambos";
  }) => Promise<void>;
  onVerifyDeadlines: (systemId?: number | null) => Promise<void>;
  onMarkAwardClosed: (id: number) => Promise<void>;
  onUpdatePipeline: (id: number, status: PipelineStatus, notes?: string) => Promise<void>;
}

const PIPELINE_OPTIONS: { value: PipelineStatus; label: string }[] = [
  { value: "novo", label: "Novo" },
  { value: "analisando", label: "Em Análise" },
  { value: "inscrito", label: "Inscrito" },
  { value: "premiado", label: "Premiado" },
  { value: "descartado", label: "Descartado" },
];

type StatusTab = "todos" | "abertos" | "previstos" | "encerrados";

function classifyAwardBucket(a: AwardOpportunity): "aberto" | "previsto" | "encerrado" {
  if (a.is_open_for_application && a.award_status === "aberto") return "aberto";
  if (a.award_status === "previsto" || a.award_status === "recorrente") return "previsto";
  return "encerrado";
}

export function AwardsPage({
  systems,
  awards,
  initialSystemId,
  onRunAwardsScan,
  onVerifyDeadlines,
  onMarkAwardClosed,
  onUpdatePipeline,
}: Props) {
  const [scanSystemId, setScanSystemId] = useState<string>(initialSystemId ? String(initialSystemId) : "");
  const [scanScope, setScanScope] = useState<"todos" | "internacional" | "nacional">("todos");
  const [scanAiMode, setScanAiMode] = useState<"auto" | "com_ia" | "sem_ia" | "ambos">("auto");
  const [scanning, setScanning] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Full catalog (open + upcoming + expired history) for differentiated display
  const [allAwards, setAllAwards] = useState<AwardOpportunity[]>(awards);
  const [statusTab, setStatusTab] = useState<StatusTab>("todos");

  // Filters
  const [filterScope, setFilterScope] = useState("");
  const [filterAi, setFilterAi] = useState("");
  const [filterStage, setFilterStage] = useState("");
  const [filterPipeline, setFilterPipeline] = useState("");
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"both" | "map" | "list">("both");

  useEffect(() => {
    setScanSystemId(initialSystemId ? String(initialSystemId) : "");
  }, [initialSystemId]);

  const loadAllAwards = useCallback(async () => {
    try {
      const full = await api.listAwards({
        system_id: scanSystemId ? Number(scanSystemId) : undefined,
        include_upcoming_cycles: true,
        include_expired: true,
      });
      setAllAwards(full);
    } catch {
      setAllAwards(awards);
    }
  }, [scanSystemId, awards]);

  useEffect(() => {
    loadAllAwards();
  }, [loadAllAwards]);

  const handleCopy = async (id: number, url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // ignore clipboard errors
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await onRunAwardsScan({
        system_id: scanSystemId ? Number(scanSystemId) : null,
        focus_scope: scanScope,
        include_ai_filter: scanAiMode,
      });
      await loadAllAwards();
    } finally {
      setScanning(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      await onVerifyDeadlines(scanSystemId ? Number(scanSystemId) : null);
      await loadAllAwards();
    } finally {
      setVerifying(false);
    }
  };

  const baseFiltered = allAwards.filter((a) => {
    if (scanSystemId && String(a.system_id) !== scanSystemId) return false;
    if (filterScope && a.scope !== filterScope) return false;
    if (filterAi && a.ai_requirement !== filterAi) return false;
    if (filterStage && a.stage_eligibility !== filterStage) return false;
    if (filterPipeline && a.pipeline_status !== filterPipeline) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      const hay = `${a.title} ${a.organizer} ${a.description} ${a.country_region} ${a.country} ${a.city} ${a.system_name}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const openList = baseFiltered.filter((a) => classifyAwardBucket(a) === "aberto");
  const upcomingList = baseFiltered.filter((a) => classifyAwardBucket(a) === "previsto");
  const closedList = baseFiltered.filter((a) => classifyAwardBucket(a) === "encerrado");

  const mapAwards =
    statusTab === "abertos"
      ? openList
      : statusTab === "previstos"
      ? upcomingList
      : statusTab === "encerrados"
      ? closedList
      : baseFiltered;

  const renderAwardCard = (a: AwardOpportunity, bucket: "aberto" | "previsto" | "encerrado") => {
    const directUrl = normalizeExternalUrl(a.official_url);
    const targetUrl = directUrl || buildFallbackSearchUrl(`${a.title} ${a.organizer}`);
    const isClosed = bucket === "encerrado";
    const isUpcoming = bucket === "previsto";

    const cardTone =
      bucket === "aberto"
        ? "border-emerald-300 bg-white shadow-sm ring-1 ring-emerald-100 hover:border-emerald-400"
        : isUpcoming
        ? "border-amber-200 bg-amber-50/35 shadow-sm hover:border-amber-300"
        : "border-dashed border-slate-300 bg-slate-50/80 opacity-85 hover:opacity-100";

    return (
      <div key={a.id} className={`rounded-2xl border p-5 transition ${cardTone}`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              {bucket === "aberto" ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2.5 py-0.5 text-[11px] font-bold uppercase text-white shadow-sm">
                  <CheckCircle2 className="h-3 w-3" /> Inscrições Abertas
                </span>
              ) : isUpcoming ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-500 px-2.5 py-0.5 text-[11px] font-bold uppercase text-white">
                  <Clock className="h-3 w-3" /> Próximo Ciclo (Previsto)
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-500 px-2.5 py-0.5 text-[11px] font-bold uppercase text-white">
                  <Archive className="h-3 w-3" /> Inscrições Encerradas
                </span>
              )}

              <span className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700">
                <Award className="h-3.5 w-3.5" /> {a.system_name}
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold ${
                  isClosed ? "bg-slate-200/80 text-slate-600" : "bg-emerald-50 text-emerald-800"
                }`}
              >
                <MapPin className="h-3 w-3" />
                {a.city ? `${a.city}, ${a.country}` : a.country_region} ({a.scope})
              </span>
              <span className="inline-flex items-center gap-1 rounded-md bg-cyan-50 px-2 py-0.5 text-xs font-medium text-cyan-800">
                <Cpu className="h-3 w-3" />
                {a.ai_requirement === "ambos"
                  ? "Com ou Sem IA"
                  : a.ai_requirement === "com_ia"
                  ? "Foco em IA"
                  : "Sem IA"}
              </span>
              {a.discovery_source === "gemini_global_search" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2 py-0.5 text-[11px] font-semibold text-purple-700">
                  <Sparkles className="h-3 w-3" /> Descoberto ao vivo
                </span>
              )}
            </div>

            <h3 className={`text-lg font-bold ${isClosed ? "text-slate-600" : "text-slate-900"}`}>
              <a
                href={targetUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 hover:text-indigo-700 hover:underline"
              >
                <span>{a.title}</span>
                <ExternalLink className="h-4 w-4 shrink-0 text-indigo-500" />
              </a>
            </h3>
            <p className="text-xs font-medium text-slate-500">Organização: {a.organizer}</p>
          </div>

          <div className="flex items-center gap-2.5">
            <MatchScoreBadge score={a.match_score} />
            <select
              value={a.pipeline_status}
              onChange={(e) => onUpdatePipeline(a.id, e.target.value as PipelineStatus)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700"
            >
              {PIPELINE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <p className={`mt-3 text-sm ${isClosed ? "text-slate-500" : "text-slate-700"}`}>{a.description}</p>

        <div className="mt-4 grid gap-3 rounded-xl bg-slate-100/70 p-3.5 text-xs md:grid-cols-2">
          <div>
            <div className="font-semibold text-slate-800">Por que combina com seu sistema:</div>
            <p className="mt-1 text-slate-600">{a.match_reasoning}</p>
          </div>
          <div>
            <div className="font-semibold text-slate-800">Benefícios / Premiação & Próximos Passos:</div>
            <p className="mt-1 text-slate-600">{a.prize_benefits}</p>
            {!isClosed && a.next_steps && <p className="mt-1 text-indigo-700">{a.next_steps}</p>}
          </div>
        </div>

        {a.deadline_source_note && (
          <div
            className={`mt-3 flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] ${
              bucket === "aberto"
                ? "bg-emerald-50 text-emerald-900"
                : isUpcoming
                ? "bg-amber-100/70 text-amber-900"
                : "bg-slate-200/70 text-slate-700"
            }`}
          >
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            <span>{a.deadline_source_note}</span>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200/70 pt-3 text-xs">
          <div className="flex min-w-0 flex-wrap items-center gap-3 text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-indigo-500" />
              <strong>Prazo:</strong>{" "}
              {bucket === "aberto" && a.days_remaining !== null ? (
                <span className="font-semibold text-emerald-700">
                  Faltam {a.days_remaining} dias ({a.deadline_date}) — {a.deadline}
                </span>
              ) : (
                <span className={isClosed ? "font-medium text-slate-500 line-through" : "font-semibold text-amber-800"}>
                  {a.deadline}
                </span>
              )}
            </span>
            {directUrl && (
              <a
                href={directUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex max-w-xs items-center gap-1 truncate font-mono text-[11px] text-indigo-700 hover:underline"
                title={directUrl}
              >
                <Link2 className="h-3 w-3 shrink-0" />
                {directUrl}
              </a>
            )}
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {!isClosed && (
              <button
                type="button"
                onClick={async () => {
                  await onMarkAwardClosed(a.id);
                  await loadAllAwards();
                }}
                className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1.5 font-medium text-rose-700 hover:bg-rose-100"
                title="Mover este edital para o histórico de encerrados"
              >
                <EyeOff className="h-3.5 w-3.5" /> Prazo já passou
              </button>
            )}
            {directUrl && (
              <button
                type="button"
                onClick={() => handleCopy(a.id, directUrl)}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 font-medium text-slate-700 hover:bg-slate-50"
              >
                {copiedId === a.id ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" /> Copiado
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" /> Copiar link
                  </>
                )}
              </button>
            )}
            <a
              href={targetUrl}
              target="_blank"
              rel="noreferrer"
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-semibold text-white ${
                bucket === "aberto"
                  ? "bg-emerald-600 hover:bg-emerald-700"
                  : isUpcoming
                  ? "bg-amber-600 hover:bg-amber-700"
                  : "bg-slate-600 hover:bg-slate-700"
              }`}
            >
              {bucket === "aberto" ? "Acessar Edital Oficial" : "Ver Página / Próxima Edição"}{" "}
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header + Actions */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Radar Semanal Mundial de Premiações & Concursos
          </h2>
          <p className="text-sm text-slate-500">
            Destaca em verde o que está realmente aberto (≥ 15 dias) e separa visualmente o histórico de editais encerrados para planejar o próximo ciclo.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleVerify}
            disabled={verifying}
            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-300 bg-emerald-50 px-3.5 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
            title="Entra nas páginas oficiais e subpáginas de edital para confirmar quais inscrições estão abertas hoje"
          >
            {verifying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
            {verifying ? "Varrendo sites oficiais..." : "Verificar prazos ao vivo"}
          </button>
          <a
            href={api.exportAwardsUrl("markdown", scanSystemId ? Number(scanSystemId) : undefined)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" /> Markdown
          </a>
          <a
            href={api.exportAwardsUrl("csv", scanSystemId ? Number(scanSystemId) : undefined)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" /> CSV
          </a>
        </div>
      </div>

      {/* Global Search Control Bar */}
      <div className="rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-cyan-50 p-5 shadow-sm">
        <div className="mb-3 flex items-center gap-2 text-sm font-bold text-indigo-900">
          <Globe2 className="h-4 w-4 text-indigo-600" />
          Disparar Pesquisa Mundial Personalizada pelo Perfil do Sistema
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <select
            value={scanSystemId}
            onChange={(e) => setScanSystemId(e.target.value)}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">Todos os sistemas ativos</option>
            {systems.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.uses_ai === "sem_ia" ? "Sem IA" : "Com IA"} • {s.stage})
              </option>
            ))}
          </select>

          <select
            value={scanScope}
            onChange={(e) => setScanScope(e.target.value as typeof scanScope)}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="todos">Abrangência: Todo o Mundo + Nacional</option>
            <option value="internacional">Somente Internacionais / Globais</option>
            <option value="nacional">Somente Nacionais (Brasil)</option>
          </select>

          <select
            value={scanAiMode}
            onChange={(e) => setScanAiMode(e.target.value as typeof scanAiMode)}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="auto">IA: Automático pelo perfil do sistema</option>
            <option value="ambos">Incluir prêmios com IA e sem IA</option>
            <option value="com_ia">Focar em prêmios de IA para o Cidadão</option>
            <option value="sem_ia">Focar em prêmios que não exigem IA</option>
          </select>

          <button
            onClick={handleScan}
            disabled={scanning}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
            {scanning ? "Pesquisando & verificando..." : "Pesquisar Prêmios Agora"}
          </button>
        </div>
      </div>

      {/* Filters + Status Tabs + View Switcher */}
      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-5">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filtrar prêmio, país, cidade..."
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm"
            />
          </div>

          <select
            value={filterScope}
            onChange={(e) => setFilterScope(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Todas abrangências</option>
            <option value="internacional">Internacional</option>
            <option value="regional">Regional (LATAM/EU)</option>
            <option value="nacional">Nacional</option>
          </select>

          <select
            value={filterAi}
            onChange={(e) => setFilterAi(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Qualquer requisito IA</option>
            <option value="ambos">Aceita com ou sem IA</option>
            <option value="com_ia">Foco / Exige IA</option>
            <option value="sem_ia">Sem IA / Foco Geral</option>
          </select>

          <select
            value={filterStage}
            onChange={(e) => setFilterStage(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Qualquer estágio</option>
            <option value="ambos">Iniciativa ou Produção</option>
            <option value="iniciativa">Iniciativa / Em Dev</option>
            <option value="producao">Já em Produção</option>
          </select>

          <select
            value={filterPipeline}
            onChange={(e) => setFilterPipeline(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Todos status pipeline</option>
            {PIPELINE_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3 text-xs">
          {/* Status filter pills */}
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setStatusTab("todos")}
              className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                statusTab === "todos" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Todos ({baseFiltered.length})
            </button>
            <button
              type="button"
              onClick={() => setStatusTab("abertos")}
              className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                statusTab === "abertos"
                  ? "bg-emerald-600 text-white"
                  : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
              }`}
            >
              🟢 Abertos ≥ 15d ({openList.length})
            </button>
            <button
              type="button"
              onClick={() => setStatusTab("previstos")}
              className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                statusTab === "previstos"
                  ? "bg-amber-500 text-white"
                  : "bg-amber-50 text-amber-800 hover:bg-amber-100"
              }`}
            >
              🟡 Próximos ciclos ({upcomingList.length})
            </button>
            <button
              type="button"
              onClick={() => setStatusTab("encerrados")}
              className={`rounded-xl px-3 py-1.5 font-semibold transition ${
                statusTab === "encerrados"
                  ? "bg-slate-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              ⚪ Encerrados / Histórico ({closedList.length})
            </button>
          </div>

          <div className="inline-flex rounded-xl border border-slate-200 bg-slate-100 p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("both")}
              className={`inline-flex items-center gap-1 rounded-lg px-3 py-1 font-semibold transition ${
                viewMode === "both" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600"
              }`}
            >
              <MapIcon className="h-3.5 w-3.5" /> Mapa + Lista
            </button>
            <button
              type="button"
              onClick={() => setViewMode("map")}
              className={`inline-flex items-center gap-1 rounded-lg px-3 py-1 font-semibold transition ${
                viewMode === "map" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600"
              }`}
            >
              <Globe2 className="h-3.5 w-3.5" /> Só Mapa
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              className={`inline-flex items-center gap-1 rounded-lg px-3 py-1 font-semibold transition ${
                viewMode === "list" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600"
              }`}
            >
              <List className="h-3.5 w-3.5" /> Só Lista
            </button>
          </div>
        </div>
      </div>

      {/* Interactive World Map */}
      {(viewMode === "both" || viewMode === "map") && (
        <AwardsWorldMap
          awards={mapAwards}
          heightClass={viewMode === "map" ? "h-[600px]" : "h-[460px]"}
          showClosedToggle={statusTab === "todos"}
        />
      )}

      {/* Separated Visual Sections */}
      {(viewMode === "both" || viewMode === "list") && (
        <div className="space-y-8">
          {/* Section 1: Open Now */}
          {(statusTab === "todos" || statusTab === "abertos") && (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="flex items-center gap-2 text-base font-bold text-emerald-900">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  Inscrições Abertas Agora — Prazo ≥ 15 dias ou Fluxo Contínuo ({openList.length})
                </h3>
              </div>
              {openList.length > 0 ? (
                <div className="space-y-4">{openList.map((a) => renderAwardCard(a, "aberto"))}</div>
              ) : (
                <div className="rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/40 p-6 text-center text-sm text-emerald-800">
                  Nenhum edital com inscrições abertas confirmado neste filtro agora. Clique em{" "}
                  <strong>"Pesquisar Prêmios Agora"</strong> para buscar novas chamadas abertas.
                </div>
              )}
            </section>
          )}

          {/* Section 2: Upcoming Cycles */}
          {(statusTab === "todos" || statusTab === "previstos") && upcomingList.length > 0 && (
            <section className="space-y-3">
              <h3 className="flex items-center gap-2 text-base font-bold text-amber-900">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                Próximos Ciclos Previstos — Aguardando Abertura ({upcomingList.length})
              </h3>
              <div className="space-y-4">{upcomingList.map((a) => renderAwardCard(a, "previsto"))}</div>
            </section>
          )}

          {/* Section 3: Past / Closed History */}
          {(statusTab === "todos" || statusTab === "encerrados") && closedList.length > 0 && (
            <section className="space-y-3 border-t border-slate-200 pt-6">
              <div>
                <h3 className="flex items-center gap-2 text-base font-bold text-slate-600">
                  <Archive className="h-4 w-4 text-slate-500" />
                  Histórico — Inscrições Já Encerradas / O que ficou para trás ({closedList.length})
                </h3>
                <p className="text-xs text-slate-500">
                  Mantidos com visual diferenciado para você acompanhar premiações relevantes e se preparar para a próxima edição.
                </p>
              </div>
              <div className="space-y-3">{closedList.map((a) => renderAwardCard(a, "encerrado"))}</div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
