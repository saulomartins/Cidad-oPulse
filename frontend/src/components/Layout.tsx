import type { ReactNode } from "react";
import {
  Activity,
  AlertOctagon,
  Award,
  Cpu,
  FolderKanban,
  Layers,
  LayoutDashboard,
  LogOut,
  MapPin,
  Radio,
  Settings,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";
import type { AppSettings, MonitoredSystem } from "../types";

export type NavTab = "dashboard" | "systems" | "sentiment" | "temporal" | "problems" | "awards" | "settings";

interface Props {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  settings: AppSettings | null;
  systems: MonitoredSystem[];
  selectedProjectId: number | null;
  onSelectProject: (projectId: number | null) => void;
  authRequired?: boolean;
  authRole?: "admin" | "editor" | "viewer" | "anonymous";
  authLabel?: string;
  onLogout?: () => void;
  children: ReactNode;
}

const NAV_ITEMS: { id: NavTab; label: string; icon: typeof LayoutDashboard; badge?: string }[] = [
  { id: "dashboard", label: "Visão Geral", icon: LayoutDashboard },
  { id: "systems", label: "Sistemas Monitorados", icon: Layers },
  { id: "sentiment", label: "Monitor de Sentimento", icon: Activity },
  { id: "temporal", label: "Análise Temporal", icon: TrendingUp, badge: "7d–1a" },
  { id: "problems", label: "Diagnóstico de Dores", icon: AlertOctagon, badge: "IG/FB" },
  { id: "awards", label: "Radar Mundial de Prêmios", icon: Award, badge: "Semanal" },
  { id: "settings", label: "Conectores & Acessos", icon: Settings, badge: "Tokens" },
];

export function Layout({
  activeTab,
  onSelectTab,
  settings,
  systems,
  selectedProjectId,
  onSelectProject,
  authRequired = false,
  authRole = "admin",
  authLabel = "",
  onLogout,
  children,
}: Props) {
  const activeProject = systems.find((s) => s.id === selectedProjectId) || null;
  const visibleNavItems = NAV_ITEMS.filter((item) => item.id !== "settings" || authRole === "admin");

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col bg-slate-900 text-slate-200 lg:flex">
        <div className="flex items-center gap-3 border-b border-slate-800 px-5 py-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 text-white shadow-lg">
            <Radio className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white">CidadãoPulse</h1>
            <p className="text-[11px] text-slate-400">Sentimento & Prêmios GovTech</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`flex w-full items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-medium transition ${
                  active
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-900/40"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <span className="flex items-center gap-3">
                  <Icon className="h-4 w-4" />
                  {item.label}
                </span>
                {item.badge && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      active ? "bg-white/20 text-white" : "bg-indigo-500/20 text-indigo-300"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="m-3 rounded-xl border border-slate-800 bg-slate-800/60 p-3.5 text-xs">
          <div className="flex items-center gap-2 font-semibold text-white">
            <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
            Motor de IA
          </div>
          <p className="mt-1 text-slate-400">
            {settings?.gemini_configured ? (
              <span className="text-emerald-400">
                Gemini ativo ({settings.gemini_model}) + Google Search Grounding
              </span>
            ) : (
              <span className="text-amber-300">
                Modo aberto (RSS + Reddit + Catálogo). Configure a GEMINI_API_KEY para busca global ao vivo.
              </span>
            )}
          </p>
          {settings?.next_awards_run && (
            <p className="mt-2 border-t border-slate-700 pt-2 text-[11px] text-slate-400">
              Próximo radar semanal:{" "}
              <span className="font-medium text-slate-200">
                {new Date(settings.next_awards_run).toLocaleString("pt-BR", {
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </p>
          )}
        </div>
      </aside>

      {/* Main Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile Nav */}
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
          <div className="flex items-center gap-2 font-bold text-slate-900">
            <Radio className="h-5 w-5 text-indigo-600" />
            CidadãoPulse
          </div>
          <div className="flex gap-1 overflow-x-auto">
            {visibleNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectTab(item.id)}
                  className={`rounded-lg p-2 ${
                    activeTab === item.id
                      ? "bg-indigo-600 text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                  title={item.label}
                >
                  <Icon className="h-4 w-4" />
                </button>
              );
            })}
          </div>
        </header>

        {/* Global Project Scope Bar */}
        <div className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 px-4 py-2.5 backdrop-blur sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">
                <FolderKanban className="h-4 w-4 text-indigo-600" />
                Visão por Projeto:
              </span>
              <select
                value={selectedProjectId ?? ""}
                onChange={(e) => onSelectProject(e.target.value ? Number(e.target.value) : null)}
                className="rounded-xl border border-indigo-200 bg-indigo-50/50 px-3 py-1.5 text-sm font-semibold text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              >
                <option value="">Todos os Projetos ({systems.length}) — Visão Consolidada</option>
                {systems.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.state_uf ? ` (${s.municipality ? `${s.municipality}/` : ""}${s.state_uf})` : ""}
                  </option>
                ))}
              </select>

              {activeProject && (
                <button
                  type="button"
                  onClick={() => onSelectProject(null)}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200"
                  title="Voltar para visão consolidada de todos os projetos"
                >
                  <X className="h-3 w-3" /> Ver todos
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs">
              {activeProject ? (
                <>
                  <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 font-semibold text-indigo-700">
                    {activeProject.citizen_area}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 font-medium text-slate-700">
                    <Cpu className="h-3 w-3" />
                    {activeProject.uses_ai === "com_ia"
                      ? "Com IA"
                      : activeProject.uses_ai === "hibrido"
                      ? "Híbrido IA"
                      : "Sem IA"}
                  </span>
                  {(activeProject.municipality || activeProject.state_uf) && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 font-semibold text-emerald-700">
                      <MapPin className="h-3 w-3" />
                      {[activeProject.municipality, activeProject.state_uf].filter(Boolean).join(" / ")}
                    </span>
                  )}
                </>
              ) : (
                <span className="hidden text-xs text-slate-400 sm:inline">
                  Selecione um projeto para filtrar indicadores, gráficos, dores e mapa de premiações
                </span>
              )}

              <div className="ml-1 flex items-center gap-1.5 border-l border-slate-200 pl-2">
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                    authRole === "admin"
                      ? "bg-slate-900 text-white"
                      : authRole === "editor"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-cyan-100 text-cyan-800"
                  }`}
                >
                  <ShieldCheck className="h-3 w-3" />
                  {authRole === "admin"
                    ? authLabel || "Admin"
                    : `${authLabel || "Convidado"} (${authRole === "editor" ? "Colaborador" : "Leitura"})`}
                </span>
                {onLogout && (
                  <button
                    type="button"
                    onClick={onLogout}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-rose-50 hover:text-rose-700"
                    title="Sair / trocar usuário"
                  >
                    <LogOut className="h-3 w-3" /> Sair
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
