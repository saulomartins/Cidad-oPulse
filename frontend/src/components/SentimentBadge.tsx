import type { SentimentType } from "../types";

interface Props {
  sentiment: SentimentType;
  score?: number;
}

export function SentimentBadge({ sentiment, score }: Props) {
  const styles: Record<SentimentType, string> = {
    positivo: "bg-emerald-50 text-emerald-700 border-emerald-200",
    neutro: "bg-slate-100 text-slate-700 border-slate-200",
    negativo: "bg-rose-50 text-rose-700 border-rose-200",
  };
  const labels: Record<SentimentType, string> = {
    positivo: "Positivo",
    neutro: "Neutro",
    negativo: "Negativo",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${styles[sentiment]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          sentiment === "positivo"
            ? "bg-emerald-500"
            : sentiment === "negativo"
            ? "bg-rose-500"
            : "bg-slate-400"
        }`}
      />
      {labels[sentiment]}
      {score !== undefined && (
        <span className="font-mono text-[11px] opacity-80">
          ({score > 0 ? `+${score.toFixed(2)}` : score.toFixed(2)})
        </span>
      )}
    </span>
  );
}
