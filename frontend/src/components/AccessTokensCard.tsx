import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Check,
  Copy,
  KeyRound,
  Link2,
  Lock,
  Mail,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { api } from "../api/client";

interface TokenRow {
  id: number;
  label: string;
  role: "viewer" | "editor";
  token_prefix: string;
  is_active: boolean;
  is_expired: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  use_count: number;
  created_at: string | null;
}

export function AccessTokensCard() {
  // Access & Google Login Config
  const [passwordEnabled, setPasswordEnabled] = useState(false);
  const [passwordFromEnv, setPasswordFromEnv] = useState(false);
  const [newAdminPassword, setNewAdminPassword] = useState("");
  const [googleClientId, setGoogleClientId] = useState("");
  const [adminGoogleEmails, setAdminGoogleEmails] = useState("");
  const [allowedGoogleEmails, setAllowedGoogleEmails] = useState("");
  const [savingAccess, setSavingAccess] = useState(false);
  const [accessFeedback, setAccessFeedback] = useState<string | null>(null);

  // Guest Tokens
  const [tokens, setTokens] = useState<TokenRow[]>([]);
  const [label, setLabel] = useState("");
  const [customToken, setCustomToken] = useState("");
  const [expiresDays, setExpiresDays] = useState<string>("30");
  const [creating, setCreating] = useState(false);
  const [newlyCreated, setNewlyCreated] = useState<{ label: string; role: string; token: string } | null>(null);
  const [copied, setCopied] = useState<"token" | "link" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [rows, cfg] = await Promise.all([api.listAccessTokens(), api.getAccessConfig()]);
      setTokens(rows);
      setPasswordEnabled(cfg.password_enabled);
      setPasswordFromEnv(cfg.password_from_env);
      setGoogleClientId(cfg.google_client_id || "");
      setAdminGoogleEmails(cfg.admin_google_emails || "");
      setAllowedGoogleEmails(cfg.allowed_google_emails || "");
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("404") || msg.includes("Not Found")) {
        setError("Reinicie o servidor backend (uvicorn) para ativar as novas rotas de login, Gmail e tokens.");
      }
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleSaveAccessConfig = async (e: FormEvent) => {
    e.preventDefault();
    setSavingAccess(true);
    setAccessFeedback(null);
    setError(null);
    try {
      const res = await api.updateAccessConfig({
        app_password: newAdminPassword.trim() || undefined,
        google_client_id: googleClientId.trim(),
        admin_google_emails: adminGoogleEmails.trim(),
        allowed_google_emails: allowedGoogleEmails.trim(),
      });
      setPasswordEnabled(res.password_enabled);
      setNewAdminPassword("");
      setAccessFeedback(
        "Controle de acesso salvo! Clique em “Sair / Login” no canto superior direito para testar a tela de login."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar controle de acesso.");
    } finally {
      setSavingAccess(false);
    }
  };

  const handleDisablePassword = async () => {
    if (!window.confirm("Desativar a exigência de senha do administrador neste ambiente?")) return;
    setSavingAccess(true);
    try {
      const res = await api.updateAccessConfig({ clear_app_password: true });
      setPasswordEnabled(res.password_enabled);
      setAccessFeedback("Senha do painel desativada.");
    } finally {
      setSavingAccess(false);
    }
  };

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!label.trim() || !customToken.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await api.createAccessToken({
        label: label.trim(),
        role: "viewer",
        expires_in_days: expiresDays ? Number(expiresDays) : null,
        custom_token: customToken.trim(),
      });
      setNewlyCreated({ label: created.label, role: created.role, token: created.token });
      setLabel("");
      setCustomToken("");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar token.");
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: number, tokLabel: string) => {
    if (!window.confirm(`Revogar o token "${tokLabel}"? Quem estiver usando este token perderá o acesso imediatamente.`)) {
      return;
    }
    await api.revokeAccessToken(id);
    if (newlyCreated?.label === tokLabel) {
      setNewlyCreated(null);
    }
    await loadAll();
  };

  const copyValue = async (kind: "token" | "link", value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      setTimeout(() => setCopied(null), 2500);
    } catch {
      // ignore
    }
  };

  const magicLink = newlyCreated
    ? `${window.location.origin}/?token=${encodeURIComponent(newlyCreated.token)}`
    : "";

  return (
    <div className="space-y-5">
      {/* BLOCK 1: Admin Password & Google (Gmail) Login */}
      <form
        onSubmit={handleSaveAccessConfig}
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
              <Lock className="h-4 w-4 text-indigo-600" />
              Controle de Acesso: Senha do Admin &amp; Login com Google (Gmail)
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              Ative a tela de login definindo uma senha de administrador e/ou conectando o botão gratuito{" "}
              <strong>Entrar com Google (Gmail)</strong>.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5 text-[11px] font-semibold">
            <span
              className={`rounded-full px-2.5 py-1 ${
                passwordEnabled ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
              }`}
            >
              {passwordEnabled ? "Senha Admin ativa" : "Sem senha (aberto localmente)"}
            </span>
            <span
              className={`rounded-full px-2.5 py-1 ${
                googleClientId ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
              }`}
            >
              {googleClientId ? "Gmail ativo" : "Gmail opcional"}
            </span>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Admin Password */}
          <div className="space-y-2.5 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                <KeyRound className="h-3.5 w-3.5 text-indigo-600" />
                1. Senha do Administrador
              </span>
              {passwordEnabled && !passwordFromEnv && (
                <button
                  type="button"
                  onClick={handleDisablePassword}
                  className="text-[11px] font-semibold text-rose-600 hover:underline"
                >
                  Desativar senha
                </button>
              )}
            </div>
            <input
              type="password"
              value={newAdminPassword}
              onChange={(e) => setNewAdminPassword(e.target.value)}
              placeholder={
                passwordEnabled
                  ? "Senha já ativa (digite aqui apenas se quiser trocar)"
                  : "Crie uma senha forte para ativar a tela de login"
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs focus:border-indigo-500 focus:outline-none"
            />
            <p className="text-[11px] text-slate-500">
              Ao definir uma senha, qualquer acesso exigirá login (por senha, Gmail ou token de convidado). Use o botão{" "}
              <strong>Sair</strong> no topo direito para testar.
            </p>
          </div>

          {/* Google / Gmail OAuth */}
          <div className="space-y-2.5 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <span className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
              <Mail className="h-3.5 w-3.5 text-rose-500" />
              2. Login com Google (Gmail) — 100% Gratuito
            </span>
            <input
              value={googleClientId}
              onChange={(e) => setGoogleClientId(e.target.value)}
              placeholder="Google OAuth Client ID (ex.: 123456-abc.apps.googleusercontent.com)"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs focus:border-indigo-500 focus:outline-none"
            />
            <div className="grid gap-2 sm:grid-cols-2">
              <input
                value={adminGoogleEmails}
                onChange={(e) => setAdminGoogleEmails(e.target.value)}
                placeholder="E-mails Admin (ex.: voce@gmail.com)"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs focus:border-indigo-500 focus:outline-none"
              />
              <input
                value={allowedGoogleEmails}
                onChange={(e) => setAllowedGoogleEmails(e.target.value)}
                placeholder="E-mails Convidados (ex.: gestor@gmail.com)"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <p className="text-[11px] text-slate-500">
              Crie um <strong>ID do cliente OAuth (Web)</strong> grátis em{" "}
              <a
                href="https://console.cloud.google.com/apis/credentials"
                target="_blank"
                rel="noreferrer"
                className="font-semibold text-indigo-600 hover:underline"
              >
                Google Cloud Console → Credenciais
              </a>{" "}
              e adicione a URL do painel em <em>Origens JavaScript autorizadas</em>.
            </p>
          </div>
        </div>

        {accessFeedback && (
          <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
            {accessFeedback}
          </div>
        )}

        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={savingAccess}
            className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {savingAccess ? "Salvando..." : "Salvar Controle de Acesso"}
          </button>
        </div>
      </form>

      {/* BLOCK 2: Guest Access Tokens */}
      <div className="rounded-2xl border border-indigo-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
              <Users className="h-4 w-4 text-indigo-600" />
              3. Tokens de Acesso para Convidados (Compartilhar Painel)
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              Crie tokens individuais para gestores, equipe ou parceiros acessarem o painel sem revelar a senha do
              administrador nem suas chaves de API.
            </p>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
            <ShieldCheck className="h-3.5 w-3.5" /> {tokens.filter((t) => t.is_active).length} ativo(s)
          </span>
        </div>

        {/* Create Token Form */}
        <form onSubmit={handleCreate} className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3.5 md:grid-cols-12">
          <div className="md:col-span-3">
            <label className="mb-1 block text-[11px] font-semibold text-slate-700">
              Token / Palavra de Acesso *
            </label>
            <input
              required
              minLength={4}
              value={customToken}
              onChange={(e) => setCustomToken(e.target.value.replace(/\s+/g, ""))}
              placeholder=""
              className="w-full rounded-lg border border-indigo-300 bg-white px-3 py-2 font-mono text-xs font-semibold text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="md:col-span-3">
            <label className="mb-1 block text-[11px] font-semibold text-slate-700">
              Quem vai usar (Descrição) *
            </label>
            <input
              required
              minLength={2}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Ex.: Diretoria SEE-MG"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] font-semibold text-slate-700">Permissão</label>
            <select
              value="viewer"
              disabled
              className="w-full rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-2 text-xs font-semibold text-slate-600"
            >
              <option value="viewer">Somente Leitura</option>
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] font-semibold text-slate-700">Validade</label>
            <select
              value={expiresDays}
              onChange={(e) => setExpiresDays(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs"
            >
              <option value="7">7 dias</option>
              <option value="30">30 dias</option>
              <option value="90">90 dias</option>
              <option value="365">1 ano</option>
              <option value="">Sem validade</option>
            </select>
          </div>

          <div className="flex items-end md:col-span-2">
            <button
              type="submit"
              disabled={creating || !label.trim() || customToken.trim().length < 4}
              className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" /> {creating ? "Salvando..." : "Criar Token"}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {error}
          </div>
        )}

        {/* Newly Created Token Banner (shown once!) */}
        {newlyCreated && (
          <div className="mt-4 rounded-xl border-2 border-emerald-300 bg-emerald-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-bold text-emerald-900">
                <KeyRound className="h-4 w-4 text-emerald-600" />
                Token criado para “{newlyCreated.label}” — copie agora (não será exibido novamente!)
              </div>
              <button
                type="button"
                onClick={() => setNewlyCreated(null)}
                className="text-[11px] font-semibold text-emerald-700 hover:underline"
              >
                Fechar aviso
              </button>
            </div>

            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <code className="flex-1 break-all rounded-lg border border-emerald-200 bg-white px-3 py-2 font-mono text-xs text-slate-900">
                {newlyCreated.token}
              </code>
              <button
                type="button"
                onClick={() => copyValue("token", newlyCreated.token)}
                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
              >
                {copied === "token" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied === "token" ? "Token copiado!" : "Copiar Token"}
              </button>
              <button
                type="button"
                onClick={() => copyValue("link", magicLink)}
                className="inline-flex items-center gap-1 rounded-lg border border-emerald-600 bg-white px-3 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
                title="Envia o convidado direto para o painel já autenticado"
              >
                {copied === "link" ? <Check className="h-3.5 w-3.5" /> : <Link2 className="h-3.5 w-3.5" />}
                {copied === "link" ? "Link copiado!" : "Copiar Link Direto"}
              </button>
            </div>
            <p className="mt-2 text-[11px] text-emerald-800">
              Dica: enviando o <strong>Link Direto</strong>, a pessoa abre o painel automaticamente sem precisar digitar nada.
            </p>
          </div>
        )}

        {/* Active & Expired Tokens List */}
        <div className="mt-4">
          {tokens.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-200 py-5 text-center text-xs text-slate-400">
              Nenhum token de convidado criado ainda. Gere um acima para compartilhar o acesso com segurança.
            </p>
          ) : (
            <div className="divide-y divide-slate-100 rounded-xl border border-slate-200">
              {tokens.map((t) => (
                <div
                  key={t.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs hover:bg-slate-50/70"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-slate-900">{t.label}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          t.role === "editor"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-cyan-100 text-cyan-800"
                        }`}
                      >
                        {t.role === "editor" ? "Colaborador" : "Somente Leitura"}
                      </span>
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600">
                        {t.token_prefix}
                      </code>
                      {t.is_expired && (
                        <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700">
                          Expirado
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-slate-500">
                      <span>
                        Expira:{" "}
                        {t.expires_at ? new Date(t.expires_at).toLocaleDateString("pt-BR") : "Sem validade"}
                      </span>
                      <span>• Acessos: {t.use_count}</span>
                      {t.last_used_at && (
                        <span>• Último uso: {new Date(t.last_used_at).toLocaleString("pt-BR")}</span>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleRevoke(t.id, t.label)}
                    className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Revogar
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
