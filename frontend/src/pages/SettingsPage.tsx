import { useState, type FormEvent } from "react";
import {
  Bell,
  CheckCircle2,
  Clock,
  KeyRound,
  Loader2,
  Plug,
  Send,
  ShieldAlert,
} from "lucide-react";
import type { AppSettings, ConnectorStatus, JobRun, NotificationLog } from "../types";
import { AccessTokensCard } from "../components/AccessTokensCard";

interface Props {
  settings: AppSettings | null;
  connectors: ConnectorStatus[];
  jobs: JobRun[];
  notificationLogs: NotificationLog[];
  onSaveSettings: (data: Record<string, unknown>) => Promise<void>;
  onTestNotification: () => Promise<{ results: { channel: string; status: string; details: string }[] }>;
  onOpenJobResults: (jobType: string, systemId: number | null) => void;
}

const WEEKDAYS = [
  { value: "mon", label: "Segunda-feira" },
  { value: "tue", label: "Terça-feira" },
  { value: "wed", label: "Quarta-feira" },
  { value: "thu", label: "Quinta-feira" },
  { value: "fri", label: "Sexta-feira" },
  { value: "sat", label: "Sábado" },
  { value: "sun", label: "Domingo" },
];

export function SettingsPage({
  settings,
  connectors,
  jobs,
  notificationLogs,
  onSaveSettings,
  onTestNotification,
  onOpenJobResults,
}: Props) {
  const [geminiKey, setGeminiKey] = useState("");
  const [geminiModel, setGeminiModel] = useState(settings?.gemini_model ?? "gemini-4-hydrogen");
  const [youtubeKey, setYoutubeKey] = useState("");
  const [apifyToken, setApifyToken] = useState("");
  const [xToken, setXToken] = useState("");
  const [metaToken, setMetaToken] = useState("");

  const [awardsDay, setAwardsDay] = useState(settings?.awards_cron_day ?? "mon");
  const [awardsHour, setAwardsHour] = useState(settings?.awards_cron_hour ?? 8);
  const [sentimentInterval, setSentimentInterval] = useState(settings?.sentiment_interval_hours ?? 12);
  const [schedulerEnabled, setSchedulerEnabled] = useState(settings?.scheduler_enabled ?? true);

  const [webhookProvider, setWebhookProvider] = useState(settings?.webhook_provider ?? "slack");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [smtpHost, setSmtpHost] = useState(settings?.smtp_host ?? "");
  const [smtpPort, setSmtpPort] = useState(settings?.smtp_port ?? 587);
  const [smtpUser, setSmtpUser] = useState(settings?.smtp_user ?? "");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFrom, setSmtpFrom] = useState(settings?.smtp_from ?? "");
  const [alertEmailTo, setAlertEmailTo] = useState(settings?.alert_email_to ?? "");

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);
    try {
      const payload: Record<string, unknown> = {
        gemini_model: geminiModel,
        awards_cron_day: awardsDay,
        awards_cron_hour: Number(awardsHour),
        sentiment_interval_hours: Number(sentimentInterval),
        scheduler_enabled: schedulerEnabled,
        webhook_provider: webhookProvider,
        smtp_host: smtpHost,
        smtp_port: Number(smtpPort),
        smtp_user: smtpUser,
        smtp_from: smtpFrom,
        alert_email_to: alertEmailTo,
      };
      if (geminiKey.trim()) payload.gemini_api_key = geminiKey.trim();
      if (youtubeKey.trim()) payload.youtube_api_key = youtubeKey.trim();
      if (apifyToken.trim()) payload.apify_token = apifyToken.trim();
      if (xToken.trim()) payload.x_bearer_token = xToken.trim();
      if (metaToken.trim()) payload.meta_access_token = metaToken.trim();
      if (webhookUrl.trim()) payload.webhook_url = webhookUrl.trim();
      if (smtpPassword.trim()) payload.smtp_password = smtpPassword.trim();

      await onSaveSettings(payload);
      setGeminiKey("");
      setYoutubeKey("");
      setApifyToken("");
      setXToken("");
      setMetaToken("");
      setWebhookUrl("");
      setSmtpPassword("");
      setFeedback("Configurações salvas e agendador atualizado com sucesso.");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setFeedback(null);
    try {
      const res = await onTestNotification();
      const summary = res.results.map((r) => `${r.channel}: ${r.status} (${r.details})`).join(" | ");
      setFeedback(`Resultado do teste de alerta — ${summary}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Conectores Modulares, Agendador Semanal & Alertas
        </h2>
        <p className="text-sm text-slate-500">
          Configure sua chave Gemini para busca global ao vivo, conecte redes sociais opcionais e defina alertas automáticos.
        </p>
      </div>

      {feedback && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
          {feedback}
        </div>
      )}

      {/* Guest Access Tokens (Admin shares panel with others) */}
      <AccessTokensCard />

      {/* Connectors Grid */}
      <section className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
          <Plug className="h-4 w-4 text-indigo-600" />
          Status dos Conectores de Coleta
        </h3>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {connectors.map((c) => (
            <div key={c.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-bold text-slate-900">{c.name}</h4>
                {c.configured ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3 w-3" /> Ativo
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700">
                    <ShieldAlert className="h-3 w-3" /> Chave opcional
                  </span>
                )}
              </div>
              <p className="mt-1.5 text-xs text-slate-500">{c.description}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {c.platforms.map((p) => (
                  <span key={p} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <form onSubmit={handleSave} className="grid gap-6 lg:grid-cols-2">
        {/* API Keys */}
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <KeyRound className="h-4 w-4 text-indigo-600" />
            Chaves de IA & Redes Sociais Plugáveis
          </h3>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              GEMINI_API_KEY{" "}
              {settings?.gemini_configured && (
                <span className="font-normal text-emerald-600">
                  (Configurada: {settings.gemini_api_key_masked})
                </span>
              )}
            </label>
            <input
              type="password"
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
              placeholder="Cole sua nova chave do Google AI Studio..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Modelo Gemini</label>
            <select
              value={geminiModel}
              onChange={(e) => setGeminiModel(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="gemini-4-hydrogen">gemini-4-hydrogen (Recomendado — rápido e equilibrado)</option>
              <option value="gemini-4-argon">gemini-4-argon (Raciocínio avançado e pesquisa)</option>
              <option value="gemini-3.5-flash-lite">gemini-3.5-flash-lite (Ultra-rápido / alto volume)</option>
            </select>
          </div>

          <div className="grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                YouTube API Key {settings?.youtube_configured && <span className="text-emerald-600">✓</span>}
              </label>
              <input
                type="password"
                value={youtubeKey}
                onChange={(e) => setYoutubeKey(e.target.value)}
                placeholder="YOUTUBE_API_KEY"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Apify Token (IG/TikTok/FB) {settings?.apify_configured && <span className="text-emerald-600">✓</span>}
              </label>
              <input
                type="password"
                value={apifyToken}
                onChange={(e) => setApifyToken(e.target.value)}
                placeholder="APIFY_TOKEN"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                X (Twitter) Bearer Token {settings?.x_configured && <span className="text-emerald-600">✓</span>}
              </label>
              <input
                type="password"
                value={xToken}
                onChange={(e) => setXToken(e.target.value)}
                placeholder="X_BEARER_TOKEN"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Meta Graph Token {settings?.meta_configured && <span className="text-emerald-600">✓</span>}
              </label>
              <input
                type="password"
                value={metaToken}
                onChange={(e) => setMetaToken(e.target.value)}
                placeholder="META_ACCESS_TOKEN"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
              />
            </div>
          </div>
        </div>

        {/* Scheduler + Alerts */}
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <Clock className="h-4 w-4 text-indigo-600" />
            Agendamento Automático (Semanal & Sentimento)
          </h3>

          <label className="flex items-center gap-2 text-xs font-semibold text-slate-700">
            <input
              type="checkbox"
              checked={schedulerEnabled}
              onChange={(e) => setSchedulerEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Ativar agendador automático em segundo plano
          </label>

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Dia do Radar Semanal
              </label>
              <select
                value={awardsDay}
                onChange={(e) => setAwardsDay(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              >
                {WEEKDAYS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Hora (0–23)</label>
              <input
                type="number"
                min={0}
                max={23}
                value={awardsHour}
                onChange={(e) => setAwardsHour(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Sentimento a cada (h)
              </label>
              <input
                type="number"
                min={1}
                max={168}
                value={sentimentInterval}
                onChange={(e) => setSentimentInterval(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
            </div>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <h4 className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-600">
              <Bell className="h-3.5 w-3.5 text-indigo-600" />
              Alertas por Webhook (Slack / Teams) e E-mail (SMTP)
            </h4>

            <div className="grid gap-3 sm:grid-cols-3">
              <select
                value={webhookProvider}
                onChange={(e) => setWebhookProvider(e.target.value)}
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              >
                <option value="slack">Slack Webhook</option>
                <option value="teams">Microsoft Teams</option>
                <option value="generic">Webhook JSON Genérico</option>
              </select>
              <input
                type="password"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder={
                  settings?.webhook_configured ? "Webhook já configurado (cole para trocar)" : "https://hooks.slack.com/..."
                }
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs sm:col-span-2"
              />
            </div>

            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
              <input
                value={smtpHost}
                onChange={(e) => setSmtpHost(e.target.value)}
                placeholder="SMTP Host (ex: smtp.gmail.com)"
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
              <input
                type="number"
                value={smtpPort}
                onChange={(e) => setSmtpPort(Number(e.target.value))}
                placeholder="Porta (587)"
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
              <input
                value={smtpUser}
                onChange={(e) => setSmtpUser(e.target.value)}
                placeholder="Usuário SMTP"
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
              <input
                type="password"
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                placeholder="Senha / App Password SMTP"
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
              <input
                value={smtpFrom}
                onChange={(e) => setSmtpFrom(e.target.value)}
                placeholder="Remetente (From)"
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
              <input
                value={alertEmailTo}
                onChange={(e) => setAlertEmailTo(e.target.value)}
                placeholder="Destinatários (separados por vírgula)"
                className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={handleTest}
              disabled={testing}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              Testar Alerta
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Salvando..." : "Salvar Configurações"}
            </button>
          </div>
        </div>
      </form>

      {/* Execution & Notification History */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-bold text-slate-900">Histórico de Execuções (Jobs)</h3>
          <div className="space-y-2.5 text-xs">
            {jobs.slice(0, 8).map((j) => (
              <div key={j.id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-slate-800">
                    {j.job_type === "awards_radar" ? "Radar Mundial de Prêmios" : "Varredura de Sentimento"}{" "}
                    <span className="font-normal text-slate-500">({j.trigger})</span>
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] uppercase ${
                      j.status === "completed"
                        ? "bg-emerald-100 text-emerald-700"
                        : j.status === "failed"
                        ? "bg-rose-100 text-rose-700"
                        : "bg-indigo-100 text-indigo-700"
                    }`}
                  >
                    {j.status}
                  </span>
                </div>
                <p className="mt-1 text-slate-600">{j.summary || j.error_message}</p>
                <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-400">
                  <span>{new Date(j.started_at).toLocaleString("pt-BR")}</span>
                  {j.status === "completed" && (
                    <button
                      type="button"
                      onClick={() => onOpenJobResults(j.job_type, j.system_id)}
                      className="font-semibold text-indigo-600 hover:underline"
                    >
                      Acessar encontrados →
                    </button>
                  )}
                </div>
              </div>
            ))}
            {jobs.length === 0 && (
              <p className="py-6 text-center text-slate-400">Nenhuma execução registrada ainda.</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-bold text-slate-900">Log de Notificações Enviadas</h3>
          <div className="space-y-2.5 text-xs">
            {notificationLogs.slice(0, 8).map((n) => (
              <div key={n.id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-slate-800">
                    [{n.channel.toUpperCase()}] {n.title}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] uppercase ${
                      n.status === "sent"
                        ? "bg-emerald-100 text-emerald-700"
                        : n.status === "failed"
                        ? "bg-rose-100 text-rose-700"
                        : "bg-slate-200 text-slate-600"
                    }`}
                  >
                    {n.status}
                  </span>
                </div>
                <p className="mt-1 text-slate-600">{n.details}</p>
                <p className="mt-1 text-[11px] text-slate-400">
                  {new Date(n.created_at).toLocaleString("pt-BR")}
                </p>
              </div>
            ))}
            {notificationLogs.length === 0 && (
              <p className="py-6 text-center text-slate-400">Nenhum alerta enviado ainda.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
