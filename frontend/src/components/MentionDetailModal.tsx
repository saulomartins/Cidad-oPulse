import { useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
  FileText,
  MessageSquare,
  MessageSquareQuote,
  X,
} from "lucide-react";
import type { Mention } from "../types";
import { SentimentBadge } from "./SentimentBadge";
import { buildFallbackSearchUrl, getDisplayHost, normalizeExternalUrl } from "../utils/links";

interface Props {
  mention: Mention;
  parentPost?: Mention | null;
  onClose: () => void;
}

export function MentionDetailModal({ mention, parentPost, onClose }: Props) {
  const [copiedField, setCopiedField] = useState<"text" | "link" | null>(null);

  const isComment = mention.content_type === "comment";
  const directUrl = normalizeExternalUrl(mention.url || mention.parent_post_url);
  const targetUrl = directUrl || buildFallbackSearchUrl(`${mention.system_name} ${mention.title}`);
  const host = getDisplayHost(directUrl);

  const sourceBadge =
    mention.source_connector === "apify_social" ||
    mention.source_connector === "meta_api" ||
    mention.source_connector === "youtube" ||
    mention.source_connector === "x_api"
      ? {
          label: "Coleta Direta da Plataforma",
          cls: "bg-emerald-100 text-emerald-800 border border-emerald-200",
          hint: "Texto extraído diretamente da publicação/comentário original na plataforma.",
        }
      : mention.source_connector === "google_news" || mention.source_connector === "reddit"
      ? {
          label: "Fonte Direta (Notícia / RSS)",
          cls: "bg-sky-100 text-sky-800 border border-sky-200",
          hint: "Item coletado diretamente do feed de notícias/fórum de origem.",
        }
      : {
          label: "Trecho Indexado (Busca Web)",
          cls: "bg-amber-100 text-amber-800 border border-amber-200",
          hint: "Trecho indexado por buscador público; use o link abaixo para confirmar o conteúdo completo na origem.",
        };

  const handleCopy = async (field: "text" | "link", value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      // ignore clipboard errors
    }
  };

  const toneBox =
    mention.sentiment === "positivo"
      ? "border-emerald-200 bg-emerald-50/70"
      : mention.sentiment === "negativo"
      ? "border-rose-200 bg-rose-50/70"
      : "border-slate-200 bg-slate-100/80";

  const quoteBorder =
    mention.sentiment === "positivo"
      ? "border-l-emerald-500 text-emerald-950"
      : mention.sentiment === "negativo"
      ? "border-l-rose-500 text-rose-950"
      : "border-l-slate-400 text-slate-800";

  const whyLabel =
    mention.sentiment === "positivo"
      ? "Por que é Positivo:"
      : mention.sentiment === "negativo"
      ? "Por que é Negativo:"
      : "Por que é Neutro:";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-slate-200 bg-white px-6 py-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-md bg-slate-900 px-2 py-0.5 font-bold uppercase text-white">
                {mention.platform}
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-bold uppercase ${
                  isComment ? "bg-indigo-100 text-indigo-800" : "bg-cyan-100 text-cyan-800"
                }`}
              >
                {isComment ? (
                  <>
                    <MessageSquare className="h-3 w-3" /> Comentário
                  </>
                ) : (
                  <>
                    <FileText className="h-3 w-3" /> Matéria / Publicação
                  </>
                )}
              </span>
              <span className="font-semibold text-indigo-700">{mention.system_name}</span>
              <span
                className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${sourceBadge.cls}`}
                title={sourceBadge.hint}
              >
                {sourceBadge.label}
              </span>
              {mention.is_crisis_signal && (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-600 px-2 py-0.5 text-[10px] font-bold text-white">
                  <AlertTriangle className="h-3 w-3" /> SINAL DE CRISE
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500">
              Autor/Fonte: <strong className="text-slate-700">{mention.author || mention.source_connector}</strong> •{" "}
              {new Date(mention.published_at || mention.collected_at).toLocaleString("pt-BR")}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <SentimentBadge sentiment={mention.sentiment} score={mention.sentiment_score} />
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-5 p-6">
          {/* Primary Full Content Box */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-wide text-indigo-700">
                {isComment
                  ? `Texto Completo do Comentário (${mention.author || "Usuário"})`
                  : "Texto da Matéria / Publicação"}
              </span>
              <button
                type="button"
                onClick={() => handleCopy("text", mention.content || mention.title)}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
              >
                {copiedField === "text" ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" /> Copiado
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" /> Copiar texto
                  </>
                )}
              </button>
            </div>

            {!isComment && (
              <h3 className="mb-2 text-base font-bold text-slate-900">{mention.title}</h3>
            )}

            <p className="whitespace-pre-line text-base leading-relaxed text-slate-900">
              {mention.content || mention.title}
            </p>
          </div>

          {/* Linked Parent Post (when viewing a comment!) */}
          {isComment && (
            <div className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-4">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-indigo-800">
                  <FileText className="h-3.5 w-3.5" />
                  Publicação onde este comentário foi feito
                </span>
                {parentPost && (
                  <span className="text-xs font-semibold text-indigo-700">{parentPost.author}</span>
                )}
              </div>

              {parentPost ? (
                <div className="space-y-1.5">
                  <p className="whitespace-pre-line text-sm leading-relaxed text-slate-800">
                    {parentPost.content || parentPost.title}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-slate-600">
                  {mention.title} — clique em <strong>"Abrir na origem"</strong> abaixo para visualizar a postagem diretamente no {mention.platform.toUpperCase()}.
                </p>
              )}
            </div>
          )}

          {/* Sentiment Reason + Highlighted Quote */}
          <div className={`space-y-2.5 rounded-2xl border p-4 text-xs ${toneBox}`}>
            <div className="text-sm text-slate-900">
              <strong className="font-bold">{whyLabel}</strong>{" "}
              <span>
                {mention.sentiment_reason ||
                  mention.summary ||
                  "Classificação baseada no tom geral da publicação."}
              </span>
            </div>
            {(mention.evidence_quote || mention.content) && (
              <blockquote className={`border-l-4 pl-3 text-xs italic leading-relaxed ${quoteBorder}`}>
                <span className="mb-0.5 flex items-center gap-1 text-[10px] font-bold not-italic uppercase tracking-wide opacity-75">
                  <MessageSquareQuote className="h-3 w-3" /> Trecho que justificou a nota:
                </span>
                “{mention.evidence_quote || mention.content}”
              </blockquote>
            )}

            {mention.topics.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {mention.topics.map((t) => (
                  <span
                    key={t}
                    className="rounded-full bg-white/80 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700"
                  >
                    #{t}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3.5">
          <div className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-500" title={directUrl || ""}>
            {directUrl || "Sem link direto disponível"}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {directUrl && (
              <button
                type="button"
                onClick={() => handleCopy("link", directUrl)}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
              >
                {copiedField === "link" ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" /> Link copiado
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
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700"
            >
              {directUrl ? `Abrir na origem (${host || mention.platform})` : "Pesquisar na web"}{" "}
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
