import { useState } from "react";
import {
  Activity,
  Award,
  Cpu,
  Edit3,
  Globe,
  Loader2,
  MapPin,
  Plus,
  Tag,
  Trash2,
} from "lucide-react";
import type { MonitoredSystem, ProjectStarRating, SystemPayload } from "../types";
import { SystemFormModal } from "../components/SystemFormModal";
import { StarRow } from "../components/StarRatingCard";

interface Props {
  systems: MonitoredSystem[];
  starRatings?: ProjectStarRating[];
  isAdmin?: boolean;
  onCreate: (payload: SystemPayload) => Promise<void>;
  onUpdate: (id: number, payload: SystemPayload) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onScanSentiment: (systemId: number) => Promise<void>;
  onScanAwards: (systemId: number) => Promise<void>;
  onOpenProjectDashboard: (systemId: number) => void;
  onViewMentions: (systemId: number) => void;
  onViewTemporal: (systemId: number) => void;
  onViewAwards: (systemId: number) => void;
}

export function SystemsPage({
  systems,
  starRatings = [],
  isAdmin = false,
  onCreate,
  onUpdate,
  onDelete,
  onScanSentiment,
  onScanAwards,
  onOpenProjectDashboard,
  onViewMentions,
  onViewTemporal,
  onViewAwards,
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<MonitoredSystem | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const handleOpenNew = () => {
    setEditing(null);
    setModalOpen(true);
  };

  const handleEdit = (sys: MonitoredSystem) => {
    setEditing(sys);
    setModalOpen(true);
  };

  const handleAction = async (key: string, fn: () => Promise<void>) => {
    setBusyKey(key);
    try {
      await fn();
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Sistemas & Iniciativas Monitoradas
          </h2>
          <p className="text-sm text-slate-500">
            Cadastre URLs, palavras-chave e descreva cada sistema para monitorar sentimento e localizar premiações mundiais.
          </p>
        </div>

        {isAdmin && (
          <button
            onClick={handleOpenNew}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" />
            Novo Sistema
          </button>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {systems.map((sys) => {
          const sentBusy = busyKey === `sent-${sys.id}`;
          const awardBusy = busyKey === `award-${sys.id}`;
          const sysRating = starRatings.find((r) => r.system_id === sys.id);
          return (
            <div
              key={sys.id}
              className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-bold text-slate-900">{sys.name}</h3>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                          sys.stage === "producao"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}
                      >
                        {sys.stage === "producao" ? "Em Produção" : "Iniciativa / Em Dev"}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                          sys.uses_ai === "sem_ia"
                            ? "bg-slate-100 text-slate-700"
                            : "bg-indigo-50 text-indigo-700 border border-indigo-200"
                        }`}
                      >
                        <Cpu className="h-3 w-3" />
                        {sys.uses_ai === "com_ia"
                          ? "Com IA"
                          : sys.uses_ai === "hibrido"
                          ? "Híbrido (IA)"
                          : "Sem IA"}
                      </span>
                    </div>
                    <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                      <span>
                        {sys.citizen_area} • {sys.organization_type}
                      </span>
                      {(sys.municipality || sys.state_uf) ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700">
                          <MapPin className="h-3 w-3" />
                          {[sys.municipality, sys.state_uf].filter(Boolean).join(" / ")}
                        </span>
                      ) : (
                        <span>• {sys.country}</span>
                      )}
                    </p>
                  </div>

                  {isAdmin && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleEdit(sys)}
                        className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                        title="Editar sistema"
                      >
                        <Edit3 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Remover "${sys.name}" e todos os dados coletados?`)) {
                            onDelete(sys.id);
                          }
                        }}
                        className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                        title="Excluir sistema"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>

                <p className="text-sm leading-relaxed text-slate-700">{sys.description}</p>

                {sysRating && (
                  <div className="rounded-xl border border-amber-200/80 bg-amber-50/50 p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-base font-extrabold text-slate-900">
                          {sysRating.total_mentions > 0
                            ? sysRating.stars.toFixed(1).replace(".", ",")
                            : "—"}
                        </span>
                        <StarRow stars={sysRating.stars} size="sm" />
                        <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-amber-900 shadow-sm">
                          {sysRating.rating_label}
                        </span>
                      </div>
                      <span className="text-[11px] font-medium text-slate-500">
                        {sysRating.total_mentions} avaliações
                      </span>
                    </div>
                    <p className="mt-1.5 leading-relaxed text-slate-700">{sysRating.rating_reason}</p>
                  </div>
                )}

                {sys.ai_details && (
                  <p className="rounded-lg bg-indigo-50/60 px-3 py-2 text-xs text-indigo-900">
                    <strong>Uso de IA:</strong> {sys.ai_details}
                  </p>
                )}

                {/* URLs */}
                {sys.urls.length > 0 && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                      <Globe className="h-3.5 w-3.5" /> URLs monitoradas
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {sys.urls.map((u) => (
                        <a
                          key={u}
                          href={u}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-indigo-700 hover:underline"
                        >
                          {u}
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Keywords */}
                {sys.keywords.length > 0 && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                      <Tag className="h-3.5 w-3.5" /> Palavras-chave & Hashtags
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {sys.keywords.map((kw) => (
                        <span
                          key={kw}
                          className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-700"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-5 border-t border-slate-100 pt-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={() => onOpenProjectDashboard(sys.id)}
                      className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2 py-0.5 font-bold text-indigo-700 hover:bg-indigo-100"
                    >
                      Visão do projeto →
                    </button>
                    <button
                      type="button"
                      onClick={() => onViewMentions(sys.id)}
                      className="inline-flex items-center gap-1 font-medium text-slate-700 hover:text-indigo-700 hover:underline"
                    >
                      <strong className="text-slate-900">{sys.mentions_count}</strong> menções →
                    </button>
                    <button
                      type="button"
                      onClick={() => onViewTemporal(sys.id)}
                      className="inline-flex items-center gap-1 font-semibold text-cyan-700 hover:underline"
                    >
                      Temporal (7d–1a) →
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => onViewAwards(sys.id)}
                    className="inline-flex items-center gap-1 font-semibold text-indigo-700 hover:underline"
                  >
                    <strong>{sys.awards_count}</strong> premiações →
                  </button>
                </div>

                {isAdmin && (
                  <div className="grid grid-cols-2 gap-2.5">
                    <button
                      onClick={() => handleAction(`sent-${sys.id}`, () => onScanSentiment(sys.id))}
                      disabled={sentBusy}
                      className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {sentBusy ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
                      ) : (
                        <Activity className="h-3.5 w-3.5 text-indigo-600" />
                      )}
                      Monitorar Sentimento
                    </button>

                    <button
                      onClick={() => handleAction(`award-${sys.id}`, () => onScanAwards(sys.id))}
                      disabled={awardBusy}
                      className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {awardBusy ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Award className="h-3.5 w-3.5" />
                      )}
                      Buscar Prêmios Mundiais
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {modalOpen && (
        <SystemFormModal
          initial={editing}
          onClose={() => setModalOpen(false)}
          onSave={async (payload) => {
            if (editing) {
              await onUpdate(editing.id, payload);
            } else {
              await onCreate(payload);
            }
          }}
        />
      )}
    </div>
  );
}
