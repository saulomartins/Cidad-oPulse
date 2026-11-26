import { RefreshCw, Sparkles, Star, ThumbsDown, ThumbsUp, Newspaper, MessageSquare } from "lucide-react";
import type { ProjectStarRating } from "../types";

export function StarRow({
  stars,
  size = "md",
}: {
  stars: number;
  size?: "sm" | "md" | "lg";
}) {
  const iconCls = size === "lg" ? "h-5 w-5" : size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";
  return (
    <div className="inline-flex items-center gap-0.5" aria-label={`${stars.toFixed(1)} de 5 estrelas`}>
      {[1, 2, 3, 4, 5].map((idx) => {
        const fillPct = Math.max(0, Math.min(100, (stars - (idx - 1)) * 100));
        return (
          <span key={idx} className="relative inline-block">
            <Star className={`${iconCls} text-slate-200 fill-slate-200`} />
            {fillPct > 0 && (
              <span
                className="absolute inset-0 overflow-hidden"
                style={{ width: `${fillPct}%` }}
              >
                <Star className={`${iconCls} text-amber-400 fill-amber-400`} />
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}

interface Props {
  rating: ProjectStarRating;
  compact?: boolean;
  refreshing?: boolean;
  onRefresh?: (systemId: number) => void;
  onSelectProject?: (systemId: number) => void;
}

export function StarRatingCard({
  rating,
  compact = false,
  refreshing = false,
  onRefresh,
  onSelectProject,
}: Props) {
  const badgeTone =
    rating.total_mentions === 0
      ? "bg-slate-100 text-slate-600"
      : rating.stars >= 4.0
      ? "bg-emerald-100 text-emerald-800"
      : rating.stars >= 3.0
      ? "bg-amber-100 text-amber-800"
      : "bg-rose-100 text-rose-800";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-indigo-200">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            {onSelectProject ? (
              <button
                type="button"
                onClick={() => onSelectProject(rating.system_id)}
                className="text-left text-base font-bold text-slate-900 hover:text-indigo-700 hover:underline"
              >
                {rating.system_name}
              </button>
            ) : (
              <h3 className="text-base font-bold text-slate-900">{rating.system_name}</h3>
            )}
            <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${badgeTone}`}>
              {rating.rating_label}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] text-slate-500">
            {rating.citizen_area} • Classificação estilo loja de apps baseada em notícias e comentários reais
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-0.5 text-[10px] font-semibold text-indigo-700">
            <Sparkles className="h-3 w-3" />
            {rating.analyzed_by === "sentimento_calculado" ? "Cálculo de Sentimento" : `IA (${rating.analyzed_by})`}
          </span>
          {onRefresh && (
            <button
              type="button"
              onClick={() => onRefresh(rating.system_id)}
              disabled={refreshing}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              title="Recalcular classificação por estrelas com IA"
            >
              <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin text-indigo-600" : ""}`} />
              {refreshing ? "Avaliando..." : "Recalcular"}
            </button>
          )}
        </div>
      </div>

      {/* App Store / Google Play Core Score + 5-Bar Distribution */}
      <div className="mt-4 grid items-center gap-5 sm:grid-cols-12">
        <div className="flex flex-col items-center justify-center rounded-2xl border border-amber-100 bg-gradient-to-b from-amber-50/70 to-white px-4 py-4 text-center sm:col-span-4">
          <div className="text-5xl font-extrabold tracking-tight text-slate-900">
            {rating.total_mentions > 0 ? rating.stars.toFixed(1).replace(".", ",") : "—"}
          </div>
          <div className="mt-1.5">
            <StarRow stars={rating.stars} size="lg" />
          </div>
          <p className="mt-2 text-xs font-medium text-slate-500">
            {rating.total_mentions} avaliação{rating.total_mentions === 1 ? "" : "ões"}
          </p>
        </div>

        {/* 5..1 Horizontal Bars */}
        <div className="space-y-1.5 sm:col-span-8">
          {rating.star_distribution.map((bucket) => {
            const barColor =
              bucket.stars >= 4
                ? "bg-emerald-500"
                : bucket.stars === 3
                ? "bg-amber-400"
                : "bg-rose-500";
            return (
              <div key={bucket.stars} className="flex items-center gap-2.5 text-xs">
                <span className="flex w-7 shrink-0 items-center justify-end gap-0.5 font-bold text-slate-700">
                  {bucket.stars}
                  <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                </span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${Math.max(bucket.count > 0 ? 4 : 0, bucket.pct)}%` }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right font-mono text-[11px] text-slate-500">
                  {bucket.count} ({Math.round(bucket.pct)}%)
                </span>
              </div>
            );
          })}

          {/* News vs Social Split */}
          <div className="mt-2.5 flex flex-wrap gap-2 pt-1.5 text-[11px]">
            <span className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">
              <Newspaper className="h-3 w-3 text-sky-600" />
              Notícias:{" "}
              {rating.news_stars !== null ? `${rating.news_stars.toFixed(1).replace(".", ",")}★ (${rating.news_count})` : "—"}
            </span>
            <span className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">
              <MessageSquare className="h-3 w-3 text-indigo-600" />
              Redes &amp; Comentários:{" "}
              {rating.social_stars !== null
                ? `${rating.social_stars.toFixed(1).replace(".", ",")}★ (${rating.social_count})`
                : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* WHY THIS RATING (AI Explanation) */}
      <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/50 p-3.5 text-xs leading-relaxed text-slate-800">
        <span className="mb-1 block text-[11px] font-bold uppercase tracking-wide text-indigo-800">
          Por que essa nota de {rating.total_mentions > 0 ? `${rating.stars.toFixed(1).replace(".", ",")}★` : "estrelas"}?
        </span>
        {rating.rating_reason}
      </div>

      {/* Positive vs Negative Drivers */}
      {!compact && (rating.positive_drivers.length > 0 || rating.negative_drivers.length > 0) && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {rating.positive_drivers.length > 0 && (
            <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/50 p-3 text-xs">
              <div className="mb-1.5 flex items-center gap-1.5 font-bold text-emerald-900">
                <ThumbsUp className="h-3.5 w-3.5 text-emerald-600" /> O que elevou as estrelas
              </div>
              <ul className="space-y-1 text-emerald-950">
                {rating.positive_drivers.map((d, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                    <span>{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {rating.negative_drivers.length > 0 && (
            <div className="rounded-xl border border-rose-200/80 bg-rose-50/50 p-3 text-xs">
              <div className="mb-1.5 flex items-center gap-1.5 font-bold text-rose-900">
                <ThumbsDown className="h-3.5 w-3.5 text-rose-600" /> O que puxou a nota para baixo
              </div>
              <ul className="space-y-1 text-rose-950">
                {rating.negative_drivers.map((d, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" />
                    <span>{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
