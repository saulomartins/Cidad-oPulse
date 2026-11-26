interface Props {
  score: number;
}

export function MatchScoreBadge({ score }: Props) {
  const tone =
    score >= 82
      ? "bg-emerald-600 text-white"
      : score >= 68
      ? "bg-indigo-600 text-white"
      : "bg-amber-500 text-white";

  return (
    <span
      className={`inline-flex items-center rounded-lg px-2.5 py-1 text-xs font-bold tracking-tight shadow-sm ${tone}`}
      title="Aderência calculada com base no perfil do sistema cadastrado"
    >
      {score}% Match
    </span>
  );
}
