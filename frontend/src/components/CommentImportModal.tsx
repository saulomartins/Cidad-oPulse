import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link2, Loader2, MessageSquarePlus, Upload, X } from "lucide-react";
import { api } from "../api/client";
import type { MonitoredSystem } from "../types";

interface Props {
  systems: MonitoredSystem[];
  defaultSystemId?: number | null;
  apifyConfigured: boolean;
  onClose: () => void;
  onCompleted: (message: string) => Promise<void>;
}

export function CommentImportModal({
  systems,
  defaultSystemId,
  apifyConfigured,
  onClose,
  onCompleted,
}: Props) {
  const [mode, setMode] = useState<"paste" | "post_url">("paste");
  const [systemId, setSystemId] = useState<string>(
    defaultSystemId ? String(defaultSystemId) : systems[0] ? String(systems[0].id) : ""
  );
  const [platform, setPlatform] = useState<"instagram" | "facebook" | "youtube" | "x" | "reclame_aqui" | "web">("instagram");
  const [postUrl, setPostUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [maxComments, setMaxComments] = useState(50);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setRawText(text);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!systemId) {
      setError("Selecione um sistema.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "post_url") {
        const res = await api.fetchPostComments({
          system_id: Number(systemId),
          post_url: postUrl.trim(),
          max_comments: maxComments,
        });
        await onCompleted(
          `Extração concluída: ${res.extracted} comentário(s) coletado(s), ${res.saved} novo(s) analisado(s) e salvo(s).`
        );
        onClose();
      } else {
        const res = await api.importComments({
          system_id: Number(systemId),
          platform,
          post_url: postUrl.trim(),
          raw_text: rawText,
        });
        await onCompleted(
          `Importação concluída: ${res.saved} comentário(s) novo(s) analisado(s) (${res.duplicates_skipped} duplicados ignorados). Diagnóstico de dores atualizado!`
        );
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao processar comentários.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900">
              <MessageSquarePlus className="h-5 w-5 text-indigo-600" />
              Analisar Comentários do Instagram & Facebook
            </h2>
            <p className="text-xs text-slate-500">
              Extraia comentários diretamente de um post público ou cole/importe comentários para classificar sentimento e dores.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="border-b border-slate-200 bg-slate-50 px-6 py-3">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode("paste")}
              className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
                mode === "paste"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-white text-slate-700 border border-slate-300 hover:bg-slate-100"
              }`}
            >
              Colar Comentários ou CSV (Imediato)
            </button>
            <button
              type="button"
              onClick={() => setMode("post_url")}
              className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
                mode === "post_url"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-white text-slate-700 border border-slate-300 hover:bg-slate-100"
              }`}
            >
              Extrair de URL de Post IG / FB (via Apify)
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-800">
              {error}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Sistema *</label>
              <select
                required
                value={systemId}
                onChange={(e) => setSystemId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {systems.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {mode === "paste" ? (
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Rede Social / Canal</label>
                <select
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value as typeof platform)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="instagram">Instagram</option>
                  <option value="facebook">Facebook</option>
                  <option value="youtube">YouTube</option>
                  <option value="x">X (Twitter)</option>
                  <option value="reclame_aqui">Reclame Aqui</option>
                  <option value="web">Outro / Web</option>
                </select>
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Limite de comentários</label>
                <input
                  type="number"
                  min={5}
                  max={200}
                  value={maxComments}
                  onChange={(e) => setMaxComments(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            )}
          </div>

          <div>
            <label className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              <Link2 className="h-3.5 w-3.5 text-indigo-600" />
              {mode === "post_url"
                ? "URL do Post público no Instagram ou Facebook *"
                : "URL do Post original (opcional — vincula todos os comentários ao post)"}
            </label>
            <input
              required={mode === "post_url"}
              value={postUrl}
              onChange={(e) => setPostUrl(e.target.value)}
              placeholder="https://www.instagram.com/p/... ou https://www.facebook.com/.../posts/..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs"
            />
          </div>

          {mode === "post_url" ? (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3.5 text-xs text-indigo-900">
              {apifyConfigured ? (
                <span>
                  <strong>Apify conectado!</strong> Ao clicar em extrair, o sistema puxará automaticamente os
                  comentários públicos deste post, analisará sentimento e agrupará os problemas relatados.
                </span>
              ) : (
                <span>
                  <strong>Atenção:</strong> o <code>APIFY_TOKEN</code> ainda não está configurado. Você pode
                  inserir seu token em <strong>Conectores & Alertas</strong> ou usar agora mesmo a aba{" "}
                  <strong>"Colar Comentários ou CSV"</strong> sem precisar de chave.
                </span>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-700">
                  Comentários (1 por linha, ou <code>@autor | comentário</code>, ou CSV) *
                </label>
                <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100">
                  <Upload className="h-3.5 w-3.5" /> Carregar .CSV / .TXT
                  <input type="file" accept=".csv,.txt" onChange={handleFileUpload} className="hidden" />
                </label>
              </div>
              <textarea
                required
                rows={7}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder={
                  "@prof_ana | Não consigo lançar frequência no celular, fica carregando infinito!\n" +
                  "@carlos_mg | Erro 503 no fechamento de bimestre desde ontem à noite.\n" +
                  "@juliana | Onde fica o botão para recuperar a senha no novo DED+?"
                }
                className="w-full rounded-xl border border-slate-300 p-3 font-mono text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 border-t border-slate-200 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {mode === "post_url" ? "Extrair e Analisar Comentários" : "Importar e Diagnosticar Dores"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
