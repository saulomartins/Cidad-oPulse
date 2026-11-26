import { useEffect, useRef, useState, type FormEvent } from "react";
import { Eye, EyeOff, KeyRound, Lock, Mail, Radio, ShieldCheck } from "lucide-react";

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (cfg: {
            client_id: string;
            callback: (resp: { credential?: string }) => void;
          }) => void;
          renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
        };
      };
    };
  }
}

interface Props {
  googleClientId?: string;
  onLogin: (password: string) => Promise<void>;
  onGoogleLogin?: (credential: string) => Promise<void>;
}

export function LoginScreen({
  googleClientId = "",
  onLogin,
  onGoogleLogin,
}: Props) {
  const [password, setPassword] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const googleBtnRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!googleClientId || !onGoogleLogin) return;

    const initGoogleButton = () => {
      if (!window.google?.accounts?.id || !googleBtnRef.current) return;
      googleBtnRef.current.innerHTML = "";
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async (response) => {
          if (!response.credential) return;
          setSubmitting(true);
          setError(null);
          try {
            await onGoogleLogin(response.credential);
          } catch (err) {
            setError(
              err instanceof Error
                ? err.message
                : "Seu e-mail Google não está autorizado pelo administrador."
            );
          } finally {
            setSubmitting(false);
          }
        },
      });
      window.google.accounts.id.renderButton(googleBtnRef.current, {
        theme: "outline",
        size: "large",
        width: 360,
        text: "signin_with",
        shape: "pill",
        locale: "pt-BR",
      });
    };

    const existing = document.getElementById("google-gsi-script");
    if (existing) {
      initGoogleButton();
      return;
    }

    const script = document.createElement("script");
    script.id = "google-gsi-script";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = initGoogleButton;
    document.head.appendChild(script);
  }, [googleClientId, onGoogleLogin]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onLogin(password);
    } catch {
      setError("Senha do administrador ou token de acesso inválido/expirado.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-700/60 bg-white p-8 shadow-2xl">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg">
            <Radio className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">CidadãoPulse</h1>
          <p className="mt-1 text-xs text-slate-500">
            Monitoramento de Sentimento &amp; Radar Mundial de Premiações
          </p>
        </div>

        {/* Option 1: Admin / Authorized Google (Gmail) Login */}
        <div className="mb-5">
          {googleClientId ? (
            <div className="flex flex-col items-center gap-2">
              <p className="text-xs font-semibold text-slate-700">Acesso Administrador (Gmail)</p>
              <div ref={googleBtnRef} className="flex w-full justify-center" />
              <p className="text-[11px] text-slate-500">
                Apenas o e-mail Google autorizado entra como Administrador.
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3 text-xs text-amber-900">
              <div className="flex items-center gap-2 font-bold">
                <Mail className="h-4 w-4 text-rose-600" />
                Acesso Administrador via Google (Gmail)
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-amber-800">
                Configure a variável <code>GOOGLE_CLIENT_ID</code> para ativar o botão <strong>Entrar com Google</strong>{" "}
                para o e-mail administrador autorizado.
              </p>
            </div>
          )}
        </div>

        <div className="relative my-5">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center text-[11px] uppercase">
            <span className="bg-white px-2.5 font-semibold text-slate-400">acesso por token de convidado</span>
          </div>
        </div>

        {/* Option 2: Guest Access Token */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              <KeyRound className="h-3.5 w-3.5 text-indigo-600" />
              Token de Acesso (Convidado)
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type={showSecret ? "text" : "password"}
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Ex.: PULSE2026"
                className="w-full rounded-xl border border-slate-300 py-2.5 pl-9 pr-10 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
              <button
                type="button"
                onClick={() => setShowSecret((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:text-slate-700"
                title={showSecret ? "Ocultar" : "Mostrar"}
              >
                {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="mt-1.5 text-[11px] text-slate-500">
              Digite a palavra/token de acesso fornecida pelo administrador (ex.: <code>PULSE2026</code>).
            </p>
          </div>

          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !password.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60"
          >
            <ShieldCheck className="h-4 w-4" />
            {submitting ? "Verificando..." : "Entrar no Painel"}
          </button>
        </form>
      </div>
    </div>
  );
}
