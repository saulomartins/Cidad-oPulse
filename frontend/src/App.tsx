import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { Layout, type NavTab } from "./components/Layout";
import { LoginScreen } from "./components/LoginScreen";
import { DashboardPage } from "./pages/DashboardPage";
import { SystemsPage } from "./pages/SystemsPage";
import { SentimentPage } from "./pages/SentimentPage";
import { TemporalAnalysisPage } from "./pages/TemporalAnalysisPage";
import { ProblemDiagnosticsPage } from "./pages/ProblemDiagnosticsPage";
import { AwardsPage } from "./pages/AwardsPage";
import { SettingsPage } from "./pages/SettingsPage";
import type {
  AppSettings,
  AwardOpportunity,
  ConnectorStatus,
  JobRun,
  Mention,
  MonitoredSystem,
  NotificationLog,
  PipelineStatus,
  ProjectStarRating,
  SentimentOverview,
  SystemPayload,
} from "./types";

export default function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [authenticated, setAuthenticated] = useState(true);
  const [showLoginScreen, setShowLoginScreen] = useState(false);
  const [googleClientId, setGoogleClientId] = useState("");
  const [authRole, setAuthRole] = useState<"admin" | "editor" | "viewer" | "anonymous">("admin");
  const [authLabel, setAuthLabel] = useState<string>("");
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");
  const [focusedSystemId, setFocusedSystemId] = useState<number | null>(null);
  const [systems, setSystems] = useState<MonitoredSystem[]>([]);
  const [overview, setOverview] = useState<SentimentOverview | null>(null);
  const [mentions, setMentions] = useState<Mention[]>([]);
  const [awards, setAwards] = useState<AwardOpportunity[]>([]);
  const [starRatings, setStarRatings] = useState<ProjectStarRating[]>([]);
  const [refreshingStarSystemId, setRefreshingStarSystemId] = useState<number | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [connectors, setConnectors] = useState<ConnectorStatus[]>([]);
  const [jobs, setJobs] = useState<JobRun[]>([]);
  const [notificationLogs, setNotificationLogs] = useState<NotificationLog[]>([]);
  const [toast, setToast] = useState<{
    message: string;
    actionLabel?: string;
    actionTab?: NavTab;
    actionSystemId?: number | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const showToast = (
    message: string,
    action?: { label: string; tab: NavTab; systemId?: number | null }
  ) => {
    setToast({
      message,
      actionLabel: action?.label,
      actionTab: action?.tab,
      actionSystemId: action?.systemId ?? null,
    });
    setTimeout(() => setToast(null), 9000);
  };

  const refreshAll = useCallback(async () => {
    try {
      setError(null);
      const sysFilter = focusedSystemId ?? undefined;
      const isAdmin = authRole === "admin";
      const [sys, ov, men, aw, jobList, ratingsList, adminData] = await Promise.all([
        api.listSystems(),
        api.getSentimentOverview(sysFilter),
        api.listMentions({ system_id: sysFilter, limit: 200 }),
        api.listAwards({ system_id: sysFilter }),
        api.listJobs(),
        api.getStarRatings({ systemId: sysFilter, useAi: true }).catch(() => [] as ProjectStarRating[]),
        isAdmin
          ? Promise.all([api.getSettings(), api.listConnectors(), api.listNotificationLogs()])
          : Promise.resolve([null, [], []] as [AppSettings | null, ConnectorStatus[], NotificationLog[]]),
      ]);
      const [setCfg, conn, logs] = adminData;
      setSystems(sys);
      setOverview(ov);
      setMentions(men);
      setAwards(aw);
      setStarRatings(ratingsList);
      setSettings(setCfg);
      setConnectors(conn);
      setJobs(jobList);
      setNotificationLogs(logs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao conectar com o backend FastAPI.");
    }
  }, [focusedSystemId, authRole]);

  useEffect(() => {
    let active = true;
    const bootstrapAuth = async () => {
      try {
        // Support magic share links: https://app-url/?token=cp_...
        const params = new URLSearchParams(window.location.search);
        const urlToken = params.get("token")?.trim();
        if (urlToken) {
          try {
            const loginRes = await api.login(urlToken);
            params.delete("token");
            const cleanUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}${window.location.hash}`;
            window.history.replaceState({}, "", cleanUrl);
            if (!active) return;
            setAuthRequired(loginRes.auth_required);
            setAuthenticated(loginRes.authenticated);
            setAuthRole(loginRes.role);
            setAuthLabel(loginRes.label);
            setAuthChecked(true);
            return;
          } catch {
            // Invalid magic link token -> fall through to normal status check / login screen
          }
        }

        const res = await api.getAuthStatus();
        if (!active) return;
        setAuthRequired(res.auth_required);
        setAuthenticated(res.authenticated);
        setAuthRole(res.role);
        setAuthLabel(res.label);
        setGoogleClientId(res.google_client_id || "");
        setAuthChecked(true);
      } catch {
        if (!active) return;
        setAuthChecked(true);
      }
    };

    bootstrapAuth();

    const onUnauthorized = () => {
      setAuthRequired(true);
      setAuthenticated(false);
      setAuthRole("anonymous");
      setAuthLabel("");
    };
    window.addEventListener("cidadaopulse:unauthorized", onUnauthorized);
    return () => {
      active = false;
      window.removeEventListener("cidadaopulse:unauthorized", onUnauthorized);
    };
  }, []);

  useEffect(() => {
    if (authChecked && authenticated && !showLoginScreen) {
      refreshAll();
    }
  }, [authChecked, authenticated, showLoginScreen, refreshAll]);

  const handleLogin = async (password: string) => {
    const res = await api.login(password);
    setAuthRequired(res.auth_required);
    setAuthenticated(res.authenticated);
    setAuthRole(res.role);
    setAuthLabel(res.label);
    setShowLoginScreen(false);
    if (res.role !== "admin" && activeTab === "settings") {
      setActiveTab("dashboard");
    }
  };

  const handleGoogleLogin = async (credential: string) => {
    const res = await api.loginWithGoogle(credential);
    setAuthRequired(res.auth_required);
    setAuthenticated(res.authenticated);
    setAuthRole(res.role);
    setAuthLabel(res.label);
    setShowLoginScreen(false);
    if (res.role !== "admin" && activeTab === "settings") {
      setActiveTab("dashboard");
    }
  };

  const handleLogout = async () => {
    api.logout();
    try {
      const status = await api.getAuthStatus();
      setAuthRequired(status.auth_required);
      setGoogleClientId(status.google_client_id || "");
      if (status.auth_required) {
        setAuthenticated(false);
        setAuthRole("anonymous");
        setAuthLabel("");
      }
    } catch {
      // ignore
    }
    setShowLoginScreen(true);
    setActiveTab("dashboard");
  };

  const handleRunSentiment = async (systemId?: number, lookbackDays?: number) => {
    const job = await api.triggerSentimentScan(systemId, undefined, lookbackDays);
    await refreshAll();
    showToast(job.summary || `Varredura concluída (${job.new_items} novas menções).`, {
      label: "Ver menções encontradas →",
      tab: "sentiment",
      systemId: systemId ?? null,
    });
  };

  const handleRunAwards = async (payload: {
    system_id?: number | null;
    focus_scope?: "todos" | "internacional" | "nacional";
    include_ai_filter?: "auto" | "com_ia" | "sem_ia" | "ambos";
  }) => {
    const job = await api.triggerAwardsScan(payload);
    await refreshAll();
    showToast(job.summary || `Radar concluído (${job.new_items} novas premiações).`, {
      label: "Ver premiações encontradas →",
      tab: "awards",
      systemId: payload.system_id ?? null,
    });
  };

  const handleCreateSystem = async (payload: SystemPayload) => {
    const created = await api.createSystem(payload);
    await refreshAll();
    showToast(`Sistema "${created.name}" cadastrado com sucesso!`);
  };

  const handleUpdateSystem = async (id: number, payload: SystemPayload) => {
    const updated = await api.updateSystem(id, payload);
    await refreshAll();
    showToast(`Sistema "${updated.name}" atualizado.`);
  };

  const handleDeleteSystem = async (id: number) => {
    await api.deleteSystem(id);
    await refreshAll();
    showToast("Sistema removido.");
  };

  const handleDeleteMention = async (id: number) => {
    await api.deleteMention(id);
    await refreshAll();
  };

  const handleCleanupIrrelevant = async (systemId?: number) => {
    const res = await api.cleanupIrrelevantMentions(systemId);
    await refreshAll();
    showToast(
      res.removed > 0
        ? `Limpeza concluída: ${res.removed} menção(ões) fora de contexto removida(s) de ${res.evaluated} avaliadas.`
        : `Todas as ${res.evaluated} menções já estão alinhadas ao contexto dos sistemas.`
    );
  };

  const handleUpdateAwardPipeline = async (id: number, status: PipelineStatus, notes?: string) => {
    await api.updateAwardPipeline(id, { pipeline_status: status, user_notes: notes });
    await refreshAll();
  };

  const handleVerifyAwardDeadlines = async (systemId?: number | null) => {
    const res = await api.verifyAwardDeadlines(systemId);
    await refreshAll();
    showToast(
      `Verificação ao vivo concluída (${res.checked} sites): ${res.aberto} aberto(s), ${res.previsto} previsto(s) e ${res.encerrado} encerrado(s) ocultado(s).`
    );
  };

  const handleMarkAwardClosed = async (id: number) => {
    await api.updateAwardPipeline(id, {
      award_status: "encerrado",
      deadline: "Inscrições encerradas (marcado manualmente)",
      deadline_source_note: "Marcado como encerrado pelo usuário.",
    });
    await refreshAll();
    showToast("Prêmio marcado como encerrado e removido das recomendações abertas.");
  };

  const handleSaveSettings = async (data: Record<string, unknown>) => {
    await api.updateSettings(data);
    await refreshAll();
  };

  const handleTestNotification = async () => {
    const res = await api.testNotification();
    await refreshAll();
    return res;
  };

  const handleNavigate = (tab: NavTab, systemId?: number | null) => {
    if (systemId !== undefined) {
      setFocusedSystemId(systemId);
    }
    setActiveTab(tab);
  };

  const handleRefreshStarRating = async (systemId: number) => {
    setRefreshingStarSystemId(systemId);
    try {
      const updated = await api.getStarRatings({ systemId, useAi: true, refresh: true });
      if (updated.length > 0) {
        const fresh = updated[0];
        setStarRatings((prev) =>
          prev.some((r) => r.system_id === systemId)
            ? prev.map((r) => (r.system_id === systemId ? fresh : r))
            : [...prev, fresh]
        );
        showToast(
          `Nota por estrelas de ${fresh.system_name} atualizada pela IA: ${fresh.stars.toFixed(1).replace(".", ",")}★ (${fresh.rating_label}).`
        );
      }
    } finally {
      setRefreshingStarSystemId(null);
    }
  };

  const activeProject = systems.find((s) => s.id === focusedSystemId) || null;

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-medium text-slate-500">
        Carregando CidadãoPulse...
      </div>
    );
  }

  if ((authRequired && !authenticated) || showLoginScreen) {
    return (
      <LoginScreen
        googleClientId={googleClientId}
        onLogin={handleLogin}
        onGoogleLogin={handleGoogleLogin}
      />
    );
  }

  return (
    <Layout
      activeTab={activeTab}
      onSelectTab={(tab) => handleNavigate(tab)}
      settings={settings}
      systems={systems}
      selectedProjectId={focusedSystemId}
      onSelectProject={(id) => setFocusedSystemId(id)}
      authRequired={authRequired}
      authRole={authRole}
      authLabel={authLabel}
      onLogout={handleLogout}
    >
      {error && (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          <strong>Erro de conexão com a API:</strong> {error} — verifique se o backend FastAPI está rodando na porta 8000.
        </div>
      )}

      {toast && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-900 shadow-sm">
          <span>{toast.message}</span>
          {toast.actionTab && toast.actionLabel && (
            <button
              type="button"
              onClick={() => {
                handleNavigate(toast.actionTab!, toast.actionSystemId);
                setToast(null);
              }}
              className="shrink-0 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
            >
              {toast.actionLabel}
            </button>
          )}
        </div>
      )}

      {activeTab === "dashboard" && (
        <DashboardPage
          systems={systems}
          selectedProject={activeProject}
          overview={overview}
          mentions={mentions}
          awards={awards}
          starRatings={starRatings}
          refreshingStarSystemId={refreshingStarSystemId}
          onRefreshStarRating={handleRefreshStarRating}
          onSelectProject={(id) => setFocusedSystemId(id)}
          onRunSentimentAll={() => handleRunSentiment(focusedSystemId ?? undefined)}
          onRunAwardsAll={() =>
            handleRunAwards({
              system_id: focusedSystemId ?? null,
              focus_scope: "todos",
              include_ai_filter: "auto",
            })
          }
          onNavigate={(tab) => handleNavigate(tab)}
        />
      )}

      {activeTab === "systems" && (
        <SystemsPage
          systems={systems}
          starRatings={starRatings}
          onCreate={handleCreateSystem}
          onUpdate={handleUpdateSystem}
          onDelete={handleDeleteSystem}
          onScanSentiment={(id) => handleRunSentiment(id)}
          onScanAwards={(id) =>
            handleRunAwards({ system_id: id, focus_scope: "todos", include_ai_filter: "auto" })
          }
          onOpenProjectDashboard={(id) => handleNavigate("dashboard", id)}
          onViewMentions={(id) => handleNavigate("sentiment", id)}
          onViewTemporal={(id) => handleNavigate("temporal", id)}
          onViewAwards={(id) => handleNavigate("awards", id)}
        />
      )}

      {activeTab === "sentiment" && (
        <SentimentPage
          systems={systems}
          mentions={mentions}
          overview={overview}
          initialSystemId={focusedSystemId}
          onScan={(id) => handleRunSentiment(id)}
          onCleanupIrrelevant={(id) => handleCleanupIrrelevant(id)}
          onDeleteMention={handleDeleteMention}
        />
      )}

      {activeTab === "temporal" && (
        <TemporalAnalysisPage
          systems={systems}
          allMentions={mentions}
          initialSystemId={focusedSystemId}
          onScanPeriod={(sysId, lookbackDays) => handleRunSentiment(sysId, lookbackDays)}
        />
      )}

      {activeTab === "problems" && (
        <ProblemDiagnosticsPage
          systems={systems}
          mentions={mentions}
          settings={settings}
          initialSystemId={focusedSystemId}
          onRefreshAll={refreshAll}
          onToast={(msg) => showToast(msg)}
        />
      )}

      {activeTab === "awards" && (
        <AwardsPage
          systems={systems}
          awards={awards}
          initialSystemId={focusedSystemId}
          onRunAwardsScan={handleRunAwards}
          onVerifyDeadlines={handleVerifyAwardDeadlines}
          onMarkAwardClosed={handleMarkAwardClosed}
          onUpdatePipeline={handleUpdateAwardPipeline}
        />
      )}

      {activeTab === "settings" && authRole === "admin" && (
        <SettingsPage
          settings={settings}
          connectors={connectors}
          jobs={jobs}
          notificationLogs={notificationLogs}
          onSaveSettings={handleSaveSettings}
          onTestNotification={handleTestNotification}
          onOpenJobResults={(jobType, systemId) =>
            handleNavigate(jobType === "awards_radar" ? "awards" : "sentiment", systemId)
          }
        />
      )}
    </Layout>
  );
}
